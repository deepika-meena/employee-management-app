# employee-management-app

An Employee Management System with a RESTful API for CRUD operations and department-based filtering.

## Features

- Create, read, update, and delete employee records
- Employee fields: `id`, `name`, `email`, `department`, `role`, `hire_date`
- Search/filter employees by department (`GET /employees?department=Engineering`)
- JSON responses with clear error messages

## API Endpoints

- `POST /employees` - create employee
- `GET /employees` - list employees
- `GET /employees/{id}` - get one employee
- `PUT /employees/{id}` - update employee
- `DELETE /employees/{id}` - delete employee

## Run

```bash
python employee_api.py
```

Server starts at `http://127.0.0.1:8000`.

## Test

```bash
python -m unittest discover -s tests -v
```
