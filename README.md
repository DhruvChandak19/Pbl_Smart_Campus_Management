# Smart Campus Resource Management System

A desktop-based application developed using **Python, Tkinter, and MySQL** to manage campus resources efficiently. The system integrates laboratory computers, library tables, and reading room seats into a centralized platform for resource availability, allocation, and reservation management.

## Project Overview

Managing campus resources manually can lead to scheduling conflicts, inefficient utilization, and difficulty tracking availability. This project aims to simplify campus resource management through a database-driven desktop application.

The system provides separate access for administrators, staff, and students, with features designed to support resource monitoring and reservation workflows.

## Objectives

- Centralize campus resource information.
- Track the availability of laboratory computers and study spaces.
- Simplify reading room reservation management.
- Support resource allocation and usage tracking.
- Reduce scheduling conflicts and improve resource utilization.
- Maintain structured records using a MySQL database.

## Features

- **Role-based access:** Separate login workflows for Admin, Staff, and Students.
- **Laboratory management:** Manage laboratory rooms and computer resources.
- **Resource availability:** Track resource status, including available, reserved, occupied, and maintenance states.
- **Lab allocation:** Support computer allocation and monitoring for practical sessions.
- **Reading room reservations:** Allow students to reserve seats for selected time slots.
- **Library management:** Maintain records of library tables and related resources.
- **Database integration:** Store application data using MySQL.
- **Graphical user interface:** Provide a desktop interface built with Tkinter.

*Note: Feature availability depends on the current implementation and testing status.*

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic |
| Tkinter | Desktop graphical user interface |
| MySQL | Database management |
| MySQL Connector/Python | Python-to-MySQL connectivity |
| PyInstaller | Packaging the application as a Windows executable |
| Visual Studio Code | Development environment |
| MySQL Workbench | Database administration |

## System Requirements

- Windows 10 or Windows 11
- Python 3.13 or a compatible Python version
- MySQL Server
- MySQL Workbench (recommended)
- Required Python packages listed in `requirements.txt`

## Project Structure

```text
CampusResourceManagement/
├── main.py
├── database.py
├── setup_admin.py
├── reset_admin.py
├── requirements.txt
├── database_schema.sql
├── campus.ico
└── README.md
```

The files `setup_admin.py` and `reset_admin.py` are optional utilities if they are used by the current application. Include `database_schema.sql` after preparing the database initialization script.

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/CampusResourceManagement.git
cd CampusResourceManagement
```

Replace `YOUR-USERNAME` with your GitHub username.

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure MySQL

1. Start MySQL Server.
2. Create the database named `campus_resource_db`.
3. Execute the provided `database_schema.sql` script to create the required tables.
4. Configure the database connection in `database.py` using your local MySQL settings.

**Security:** Do not commit database passwords, private credentials, or real student information to GitHub. Use local configuration or environment variables for sensitive settings.

### 5. Run the application

```bash
python main.py
```

The application requires a working MySQL connection and the appropriate database schema before use.

## Database

The application uses MySQL to maintain records related to:

- Users and access roles
- Students
- Campus resources
- Reservations
- Resource usage sessions
- Timetable and allocation data, where implemented

The database schema provided in the repository should be used to initialize the database before running the application.

## Future Enhancements

- Complete integration of timetable-based laboratory allocation.
- Improve handling of unavailable or faulty computers.
- Expand reservation validation and conflict prevention.
- Strengthen authentication and account verification.
- Add utilization reports and administrative analytics.
- Complete end-to-end testing and improve deployment reliability.

## Project Status

**Development stage:** Prototype

The application is under development and testing. Some workflows and standalone Windows packaging may require further validation.

## Contributors

Add the names of your project team members here.

- Dhruv Chandak
- Yuvraj
- Ritesh
- Rohit

## Academic Project

Developed as part of the Project-Based Learning (PBL) curriculum for Computer Science and Engineering.

**Institution:** MIT-ADT University, Pune

## License

This project is intended for academic and educational purposes. Add a formal open-source license only if you intend to distribute the project under its terms.
