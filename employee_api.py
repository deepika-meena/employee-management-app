import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Dict, List
from urllib.parse import parse_qs, urlparse


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_FIELDS = {"id", "name", "email", "department", "role", "hire_date"}


@dataclass
class Employee:
    id: str
    name: str
    email: str
    department: str
    role: str
    hire_date: str


class ValidationError(ValueError):
    pass


class EmployeeStore:
    def __init__(self) -> None:
        self._employees: Dict[str, Employee] = {}
        self._lock = Lock()

    def list(self, department: str | None = None) -> List[dict]:
        with self._lock:
            employees = [asdict(employee) for employee in self._employees.values()]
        if department is None:
            return employees
        return [employee for employee in employees if employee["department"] == department]

    def get(self, employee_id: str) -> dict | None:
        with self._lock:
            employee = self._employees.get(employee_id)
        return asdict(employee) if employee else None

    def create(self, payload: dict) -> dict:
        normalized = self._normalize_payload(payload)
        with self._lock:
            if normalized.id in self._employees:
                raise ValidationError(f"Employee with id '{normalized.id}' already exists")
            self._employees[normalized.id] = normalized
        return asdict(normalized)

    def update(self, employee_id: str, payload: dict) -> dict:
        payload = dict(payload)
        payload["id"] = employee_id
        normalized = self._normalize_payload(payload)
        with self._lock:
            if employee_id not in self._employees:
                raise KeyError(employee_id)
            self._employees[employee_id] = normalized
        return asdict(normalized)

    def delete(self, employee_id: str) -> bool:
        with self._lock:
            return self._employees.pop(employee_id, None) is not None

    @staticmethod
    def _normalize_payload(payload: dict) -> Employee:
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object")

        missing = sorted(REQUIRED_FIELDS - payload.keys())
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")

        employee_id = str(payload["id"]).strip()
        name = str(payload["name"]).strip()
        email = str(payload["email"]).strip()
        department = str(payload["department"]).strip()
        role = str(payload["role"]).strip()
        hire_date = str(payload["hire_date"]).strip()

        if not employee_id:
            raise ValidationError("id cannot be empty")
        if not name:
            raise ValidationError("name cannot be empty")
        if not department:
            raise ValidationError("department cannot be empty")
        if not role:
            raise ValidationError("role cannot be empty")
        if not EMAIL_REGEX.match(email):
            raise ValidationError("email must be a valid email address")
        try:
            date.fromisoformat(hire_date)
        except ValueError as exc:
            raise ValidationError("hire_date must be in YYYY-MM-DD format") from exc

        return Employee(
            id=employee_id,
            name=name,
            email=email,
            department=department,
            role=role,
            hire_date=hire_date,
        )


class EmployeeRequestHandler(BaseHTTPRequestHandler):
    store = EmployeeStore()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/employees":
            params = parse_qs(parsed.query)
            department = params.get("department", [None])[0]
            employees = self.store.list(department=department)
            self._send_json(HTTPStatus.OK, {"employees": employees})
            return

        employee_id = self._employee_id(parsed.path)
        if employee_id is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
            return

        employee = self.store.get(employee_id)
        if employee is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Employee not found"})
            return

        self._send_json(HTTPStatus.OK, employee)

    def do_POST(self) -> None:
        if self.path != "/employees":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
            return

        payload = self._read_json_body()
        if payload is None:
            return

        try:
            employee = self.store.create(payload)
        except ValidationError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.CREATED, employee)

    def do_PUT(self) -> None:
        employee_id = self._employee_id(self.path)
        if employee_id is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
            return

        payload = self._read_json_body()
        if payload is None:
            return

        try:
            employee = self.store.update(employee_id, payload)
        except ValidationError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except KeyError:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Employee not found"})
            return

        self._send_json(HTTPStatus.OK, employee)

    def do_DELETE(self) -> None:
        employee_id = self._employee_id(self.path)
        if employee_id is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
            return

        deleted = self.store.delete(employee_id)
        if not deleted:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Employee not found"})
            return

        self._send_json(HTTPStatus.NO_CONTENT, None)

    def _read_json_body(self) -> dict | None:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing request body"})
            return None

        try:
            length = int(content_length)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length header"})
            return None

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON"})
            return None

        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be a JSON object"})
            return None

        return payload

    def _send_json(self, status: HTTPStatus, body: dict | None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if body is None:
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        encoded = json.dumps(body).encode("utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _employee_id(path: str) -> str | None:
        if not path.startswith("/employees/"):
            return None
        employee_id = path[len("/employees/"):].strip()
        return employee_id or None

    def log_message(self, message_format: str, *args) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), EmployeeRequestHandler)
    return server


if __name__ == "__main__":
    httpd = run_server()
    print("Employee API server listening on http://127.0.0.1:8000")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
