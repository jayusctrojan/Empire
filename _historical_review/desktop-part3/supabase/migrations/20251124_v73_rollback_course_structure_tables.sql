-- Empire v7.3 - Migration 2.7 ROLLBACK: Remove Course Structure Tables
-- This file provides the rollback procedure for the course structure tables migration

-- Step 1: Drop triggers
DROP TRIGGER IF EXISTS trigger_update_lesson_counts ON course_lessons;
DROP TRIGGER IF EXISTS trigger_update_module_counts ON course_modules;

-- Step 2: Drop trigger functions
DROP FUNCTION IF EXISTS update_lesson_counts();
DROP FUNCTION IF EXISTS update_module_counts();

-- Step 3: Drop helper functions
DROP FUNCTION IF EXISTS get_course_progress(UUID, VARCHAR);
DROP FUNCTION IF EXISTS complete_lesson(UUID, VARCHAR, INTEGER, TEXT);
DROP FUNCTION IF EXISTS enroll_in_course(UUID, VARCHAR);

-- Step 4: Drop views
DROP VIEW IF EXISTS popular_courses;
DROP VIEW IF EXISTS course_statistics;

-- Step 5: Drop indexes from lesson_progress
DROP INDEX IF EXISTS idx_lesson_progress_completed_at;
DROP INDEX IF EXISTS idx_lesson_progress_user_id;
DROP INDEX IF EXISTS idx_lesson_progress_lesson_id;

-- Step 6: Drop indexes from course_enrollments
DROP INDEX IF EXISTS idx_course_enrollments_last_accessed;
DROP INDEX IF EXISTS idx_course_enrollments_enrolled_at;
DROP INDEX IF EXISTS idx_course_enrollments_user_id;
DROP INDEX IF EXISTS idx_course_enrollments_course_id;

-- Step 7: Drop indexes from course_prerequisites
DROP INDEX IF EXISTS idx_course_prerequisites_prereq_id;
DROP INDEX IF EXISTS idx_course_prerequisites_course_id;

-- Step 8: Drop indexes from course_lessons
DROP INDEX IF EXISTS idx_course_lessons_resources;
DROP INDEX IF EXISTS idx_course_lessons_not_deleted;
DROP INDEX IF EXISTS idx_course_lessons_content_type;
DROP INDEX IF EXISTS idx_course_lessons_order;
DROP INDEX IF EXISTS idx_course_lessons_module_id;

-- Step 9: Drop indexes from course_modules
DROP INDEX IF EXISTS idx_course_modules_not_deleted;
DROP INDEX IF EXISTS idx_course_modules_order;
DROP INDEX IF EXISTS idx_course_modules_course_id;

-- Step 10: Drop indexes from courses
DROP INDEX IF EXISTS idx_courses_learning_objectives;
DROP INDEX IF EXISTS idx_courses_tags;
DROP INDEX IF EXISTS idx_courses_rating;
DROP INDEX IF EXISTS idx_courses_not_deleted;
DROP INDEX IF EXISTS idx_courses_created_at;
DROP INDEX IF EXISTS idx_courses_user_id;
DROP INDEX IF EXISTS idx_courses_created_by;
DROP INDEX IF EXISTS idx_courses_title;
DROP INDEX IF EXISTS idx_courses_difficulty;
DROP INDEX IF EXISTS idx_courses_status;
DROP INDEX IF EXISTS idx_courses_department_id;

-- Step 11: Drop tables (CASCADE to handle foreign keys)
DROP TABLE IF EXISTS lesson_progress CASCADE;
DROP TABLE IF EXISTS course_enrollments CASCADE;
DROP TABLE IF EXISTS course_prerequisites CASCADE;
DROP TABLE IF EXISTS course_lessons CASCADE;
DROP TABLE IF EXISTS course_modules CASCADE;
DROP TABLE IF EXISTS courses CASCADE;

-- Step 12: Drop enum types
DROP TYPE IF EXISTS lesson_content_type CASCADE;
DROP TYPE IF EXISTS course_difficulty CASCADE;
DROP TYPE IF EXISTS course_status CASCADE;

-- Note: This rollback removes all course content and progress tracking
-- Required for Feature 6 (Course Content Addition) functionality
