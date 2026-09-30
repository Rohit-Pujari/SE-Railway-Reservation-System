# Railway Reservation System – Product Backlog

## Project Title

Railway Reservation System with Booking and Cancellation Features

## Product Backlog

| ID | User Story | Priority | Story Points | Acceptance Criteria | Status |
|---|---|---|---:|---|---|
| US-01 | As a passenger, I want to register an account so that I can use the reservation system. | High | 3 | Valid details create an account; invalid/duplicate details are rejected. | To Do |
| US-02 | As a passenger, I want to log in and log out securely so that only authorized users can access my account. | High | 3 | Valid credentials allow login; invalid credentials are rejected; logout ends the session. | To Do |
| US-03 | As a passenger, I want to search for trains using source, destination, and journey date. | High | 5 | Matching trains are displayed for valid search criteria. | To Do |
| US-04 | As a passenger, I want to view train details so that I can compare trains. | High | 3 | Train number, name, source, destination, departure, arrival and fare are displayed. | To Do |
| US-05 | As a passenger, I want to check seat availability before booking. | High | 3 | Current availability is displayed for the selected train/class. | To Do |
| US-06 | As a passenger, I want to select my preferred travel class. | High | 2 | Available classes can be selected and retained for booking. | To Do |
| US-07 | As a passenger, I want to enter passenger details so that my ticket contains correct information. | High | 3 | Required passenger details are validated and stored. | To Do |
| US-08 | As a passenger, I want the system to calculate the total fare. | High | 3 | Fare follows the configured fare rules. | To Do |
| US-09 | As a passenger, I want to book an available seat. | Critical | 5 | Booking succeeds only when a seat is available and is stored. | To Do |
| US-10 | As a passenger, I want a unique PNR/booking ID after booking. | High | 3 | Every successful booking receives a unique PNR/ID. | To Do |
| US-11 | As a passenger, I want booking confirmation and ticket details. | High | 3 | Confirmation displays PNR, passenger, train, journey, class and status. | To Do |
| US-12 | As a passenger, I want to view previous and upcoming bookings. | High | 3 | The logged-in user's bookings and statuses are displayed. | To Do |
| US-13 | As a passenger, I want to cancel a booked ticket. | Critical | 5 | A valid eligible booking can be cancelled and marked Cancelled. | To Do |
| US-14 | As a passenger, I want seat availability updated after cancellation. | High | 3 | Released seat is reflected in availability. | To Do |
| US-15 | As a passenger, I want the cancellation/refund amount calculated. | High | 3 | Refund follows configured cancellation rules. | To Do |
| US-16 | As a passenger, I want to see booking/cancellation status. | Medium | 2 | Current status is clearly displayed. | To Do |
| US-17 | As an administrator, I want to add new trains. | High | 3 | Valid train information can be added and stored. | To Do |
| US-18 | As an administrator, I want to modify train details. | High | 3 | Existing train information can be updated. | To Do |
| US-19 | As an administrator, I want to remove trains. | Medium | 3 | Removed trains are no longer offered for booking. | To Do |
| US-20 | As an administrator, I want to manage routes and schedules. | High | 5 | Routes and schedules can be added or updated and reflected in searches. | To Do |
| US-21 | As an administrator, I want to view passenger bookings. | Medium | 3 | Authorized administrator can view booking records. | To Do |
| US-22 | As an administrator, I want to manage seat availability. | High | 3 | Seat inventory remains accurate. | To Do |
| US-23 | As a system, I want to maintain booking and cancellation records. | High | 3 | Confirmed and cancelled records are stored and retrievable. | To Do |
| US-24 | As a passenger, I want payment to be processed and confirmed so that my ticket is confirmed only after successful payment. | Critical | 5 | Successful payment confirms booking; failed payment does not confirm it. | To Do |

## Non-Functional Backlog

| ID | Requirement | Priority | Story Points | Status |
|---|---|---|---:|---|
| NFR-01 | Provide a simple and easy-to-use interface. | Medium | 3 | To Do |
| NFR-02 | Protect passwords and passenger personal information. | Critical | 5 | To Do |
| NFR-03 | Implement role-based authorization. | Critical | 5 | To Do |
| NFR-04 | Prevent double booking of the same seat. | Critical | 5 | To Do |
| NFR-05 | Maintain reliable booking and cancellation data. | High | 5 | To Do |
| NFR-06 | Provide acceptable train-search performance. | Medium | 3 | To Do |
| NFR-07 | Keep the software modular and maintainable. | Medium | 5 | To Do |
| NFR-08 | Support commonly used web browsers. | Medium | 3 | To Do |

## Epics

### Epic 1 – User Management
- US-01
- US-02

### Epic 2 – Train Search & Availability
- US-03
- US-04
- US-05
- US-06

### Epic 3 – Ticket Booking & Payment
- US-07
- US-08
- US-09
- US-10
- US-11
- US-24

### Epic 4 – Booking Management & Cancellation
- US-12
- US-13
- US-14
- US-15
- US-16
- US-23

### Epic 5 – Administrator Management
- US-17
- US-18
- US-19
- US-20
- US-21
- US-22

### Epic 6 – Quality & Security
- NFR-01
- NFR-02
- NFR-03
- NFR-04
- NFR-05
- NFR-06
- NFR-07
- NFR-08
