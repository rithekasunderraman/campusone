-- CampusOne student-life queries
-- These are reference queries used by the API/agent. All student queries are
-- scoped by the authenticated student's ID (never supplied by the client).

-- 1. Accommodation
SELECT s.id, s.accommodation_type, h.name, h.block, h.room_type,
       ha.room_number, ha.bed_number, ha.academic_year
FROM students s
LEFT JOIN hostel_allocations ha ON ha.student_id = s.id
LEFT JOIN hostels h ON h.id = ha.hostel_id
WHERE s.id = :student_id;

-- 2. Clubs the student belongs to
SELECT c.id, c.name, c.category, c.description, cm.role, cm.joined_on
FROM club_memberships cm
JOIN clubs c ON c.id = cm.club_id
WHERE cm.student_id = :student_id
ORDER BY c.name;

-- 3. Upcoming events for the student's clubs
SELECT ce.id, c.name AS club_name, ce.title, ce.event_date,
       ce.start_time, ce.end_time, ce.venue
FROM club_events ce
JOIN clubs c ON c.id = ce.club_id
JOIN club_memberships cm ON cm.club_id = ce.club_id
WHERE cm.student_id = :student_id
  AND ce.event_date >= CURRENT_DATE
ORDER BY ce.event_date, ce.start_time;

-- 4. Events attended
SELECT ce.id, c.name AS club_name, ce.title, ce.event_date, ce.venue
FROM event_attendance ea
JOIN club_events ce ON ce.id = ea.event_id
JOIN clubs c ON c.id = ce.club_id
WHERE ea.student_id = :student_id
ORDER BY ce.event_date DESC;

-- 5. Events volunteered for
SELECT ce.id, c.name AS club_name, ce.title, ce.event_date,
       ev.responsibility, ev.hours, ev.status
FROM event_volunteers ev
JOIN club_events ce ON ce.id = ev.event_id
JOIN clubs c ON c.id = ce.club_id
WHERE ev.student_id = :student_id
  AND ev.status <> 'Cancelled'
ORDER BY ce.event_date DESC;

-- 6. OD usage
SELECT COALESCE(SUM(approved_hours), 0) AS used_hours
FROM od_requests
WHERE student_id = :student_id
  AND status = 'Approved';
-- Remaining = GREATEST(0, 40 - used_hours).

-- 7. OD request history
SELECT r.id, r.requested_hours, r.approved_hours, r.status,
       r.request_date, r.reason, ce.title AS event_title
FROM od_requests r
LEFT JOIN club_events ce ON ce.id = r.event_id
WHERE r.student_id = :student_id
ORDER BY r.request_date DESC;
