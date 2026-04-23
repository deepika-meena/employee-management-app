import json
import unittest
from http.client import HTTPConnection
from threading import Thread

from employee_api import EmployeeRequestHandler, EmployeeStore, run_server


class EmployeeApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        EmployeeRequestHandler.store = EmployeeStore()
        cls.server = run_server(port=0)
        cls.port = cls.server.server_address[1]
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        EmployeeRequestHandler.store = EmployeeStore()

    def request(self, method: str, path: str, payload: dict | None = None):
        """Send a JSON request to the test server and return (status, json_body)."""
        connection = HTTPConnection("127.0.0.1", self.port)
        body = None if payload is None else json.dumps(payload)
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        decoded = json.loads(raw.decode("utf-8")) if raw else None
        return response.status, decoded

    def test_crud_operations(self):
        employee = {
            "id": "1",
            "name": "Alice",
            "email": "alice@example.com",
            "department": "Engineering",
            "role": "Developer",
            "hire_date": "2024-01-15",
        }

        status, created = self.request("POST", "/employees", employee)
        self.assertEqual(status, 201)
        self.assertEqual(created["id"], "1")

        status, fetched = self.request("GET", "/employees/1")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["email"], "alice@example.com")

        status, updated = self.request(
            "PUT",
            "/employees/1",
            {
                "name": "Alice Johnson",
                "email": "alice.johnson@example.com",
                "department": "Engineering",
                "role": "Senior Developer",
                "hire_date": "2024-01-15",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["name"], "Alice Johnson")

        status, _ = self.request("DELETE", "/employees/1")
        self.assertEqual(status, 204)

        status, missing = self.request("GET", "/employees/1")
        self.assertEqual(status, 404)
        self.assertEqual(missing["error"], "Employee not found")

    def test_department_filter(self):
        employees = [
            {
                "id": "1",
                "name": "Alice",
                "email": "alice@example.com",
                "department": "Engineering",
                "role": "Developer",
                "hire_date": "2024-01-15",
            },
            {
                "id": "2",
                "name": "Bob",
                "email": "bob@example.com",
                "department": "HR",
                "role": "Specialist",
                "hire_date": "2023-11-20",
            },
        ]

        for employee in employees:
            status, _ = self.request("POST", "/employees", employee)
            self.assertEqual(status, 201)

        status, result = self.request("GET", "/employees?department=Engineering")
        self.assertEqual(status, 200)
        self.assertEqual(len(result["employees"]), 1)
        self.assertEqual(result["employees"][0]["id"], "1")

    def test_validation_error(self):
        status, body = self.request(
            "POST",
            "/employees",
            {
                "id": "3",
                "name": "Bad Email",
                "email": "not-an-email",
                "department": "Engineering",
                "role": "Developer",
                "hire_date": "2024-01-15",
            },
        )

        self.assertEqual(status, 400)
        self.assertIn("email", body["error"])

        status, body = self.request(
            "POST",
            "/employees",
            {
                "id": "bad id!",
                "name": "Bad Id",
                "email": "bad.id@example.com",
                "department": "Engineering",
                "role": "Developer",
                "hire_date": "2024-01-15",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("id", body["error"])

        status, body = self.request(
            "POST",
            "/employees",
            {
                "id": "4",
                "name": "Dot Dot",
                "email": "dot.dot@domain..com",
                "department": "Engineering",
                "role": "Developer",
                "hire_date": "2024-01-15",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("email", body["error"])


if __name__ == "__main__":
    unittest.main()
