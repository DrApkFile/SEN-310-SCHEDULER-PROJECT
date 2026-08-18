# Solace Wellness Spot Scheduler — Submission

**Course:** SEN 310 — Software Engineering
**Project:** Solace Wellness Spot Scheduler (Django)

## Project Description

Solace Wellness Spot Scheduler is a Django web application that manages appointment booking for a wellness spa offering massage, acupuncture, facials, and yoga sessions. It supports three roles — **Client**, **Practitioner**, and **Admin/Manager** — each with its own dashboard. Clients browse services and book time slots validated in real time against a practitioner's declared availability and existing bookings. Appointments move through a lifecycle (pending → confirmed/declined → completed/cancelled), with each transition triggering an in-app notification and email. Admins get a reporting dashboard covering revenue, booking status, and popular services.

## Included Documents

| Document | Description | Link |
|---|---|---|
| Use Case Diagram | Actors (Client, Practitioner, Admin) and their system-level use cases | https://claude.ai/code/artifact/6743fa42-178d-46ff-8cbb-3db9f19c56f4 |
| Sequence Diagram | Booking → validation → notification → practitioner accept/decline flow | https://claude.ai/code/artifact/29fdc5a2-5675-419d-ada9-f6990a9176a2 |
| Class Diagram | Domain model: User, Service, Practitioner, Availability, Appointment, Notification | https://claude.ai/code/artifact/da117ea7-f7b1-4396-bece-10e2230c5a33 |
| User Stories | Requirements written per role (Client, Practitioner, Admin) | https://claude.ai/code/artifact/6f628834-cb41-4dfe-9aae-d4f43502ca68 |

Source HTML for each document is also kept locally under [`docs/`](docs/) for reference and future edits:
- `docs/use_case_diagram.html`
- `docs/sequence_diagram.html`
- `docs/class_diagram.html`
- `docs/user_stories.html`

## Exporting as PDF

Each link above is a live, viewable page. To turn one into a PDF for submission:

1. Open the link in a browser.
2. Press `Ctrl+P` (Windows) to open the print dialog.
3. Set **Destination** to "Save as PDF".
4. Save.

Repeat for each of the four documents to get four separate PDFs.
