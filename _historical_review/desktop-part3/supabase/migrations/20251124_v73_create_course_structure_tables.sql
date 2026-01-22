-- Empire v7.3 - Migration 2.7: Create Course Structure Tables
-- Task: Create tables for course management with progress tracking (Feature 6)
--
-- Feature 6: Course Content Addition
-- Goal: Enable structured learning paths with Course → Module → Lesson hierarchy
-- Target: Complete CRUD operations with progress tracking and knowledge base integration

-- Step 1: Create course_status enum
CREATE TYPE course_status AS ENUM (
    'draft',
    'published',
    'archived'
);

-- Step 2: Create course_difficulty enum
CREATE TYPE course_difficulty AS ENUM (
    'beginner',
    'intermediate',
    'advanced'
);

-- Step 3: Create lesson_content_type enum
CREATE TYPE lesson_content_type AS ENUM (
    'video',
    'text',
    'quiz',
    'interactive',
    'document'
);

-- Step 4: Create courses table
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Course identification and metadata
    title VARCHAR(200) NOT NULL,
    description TEXT,
    department_id INTEGER CHECK (department_id >= 1 AND department_id <= 12),

    -- Course settings
    status course_status DEFAULT 'draft' NOT NULL,
    difficulty course_difficulty,
    estimated_hours INTEGER CHECK (estimated_hours >= 1),

    -- Learning objectives and tags
    learning_objectives TEXT[], -- Array of learning objective strings
    tags TEXT[], -- Array of course tags

    -- Statistics
    module_count INTEGER DEFAULT 0 CHECK (module_count >= 0),
    lesson_count INTEGER DEFAULT 0 CHECK (lesson_count >= 0),
    enrolled_count INTEGER DEFAULT 0 CHECK (enrolled_count >= 0),
    completion_rate NUMERIC(4, 2) CHECK (completion_rate >= 0 AND completion_rate <= 100),
    rating NUMERIC(2, 1) CHECK (rating >= 0 AND rating <= 5),

    -- User tracking
    created_by VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Step 5: Create course_modules table
CREATE TABLE course_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Module relationships
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,

    -- Module metadata
    title VARCHAR(200) NOT NULL,
    description TEXT,
    module_order INTEGER NOT NULL CHECK (module_order >= 1),
    estimated_hours INTEGER CHECK (estimated_hours >= 1),

    -- Learning objectives
    learning_objectives TEXT[],

    -- Statistics
    lesson_count INTEGER DEFAULT 0 CHECK (lesson_count >= 0),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,

    -- Unique constraint for module order within a course
    CONSTRAINT unique_course_module_order UNIQUE (course_id, module_order)
);

-- Step 6: Create course_lessons table
CREATE TABLE course_lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Lesson relationships
    module_id UUID NOT NULL REFERENCES course_modules(id) ON DELETE CASCADE,

    -- Lesson metadata
    title VARCHAR(200) NOT NULL,
    description TEXT,
    lesson_order INTEGER NOT NULL CHECK (lesson_order >= 1),

    -- Content information
    content_type lesson_content_type NOT NULL,
    content_url TEXT,
    markdown_content TEXT,
    estimated_minutes INTEGER CHECK (estimated_minutes >= 1),

    -- Resources (PDFs, links, etc.)
    resources JSONB DEFAULT '[]'::jsonb,
    -- Structure: [
    --   {"type": "pdf", "title": "Cheat Sheet", "url": "https://..."},
    --   {"type": "video", "title": "Tutorial", "url": "https://..."}
    -- ]

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE,

    -- Unique constraint for lesson order within a module
    CONSTRAINT unique_module_lesson_order UNIQUE (module_id, lesson_order)
);

-- Step 7: Create course_prerequisites table (many-to-many)
CREATE TABLE course_prerequisites (
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    prerequisite_course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    PRIMARY KEY (course_id, prerequisite_course_id),

    -- Prevent self-referencing prerequisites
    CONSTRAINT no_self_prerequisite CHECK (course_id != prerequisite_course_id)
);

-- Step 8: Create course_enrollments table
CREATE TABLE course_enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Enrollment relationships
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,

    -- Progress tracking
    overall_progress NUMERIC(4, 2) DEFAULT 0.0 CHECK (overall_progress >= 0 AND overall_progress <= 100),
    completed_lessons INTEGER DEFAULT 0,
    time_spent_minutes INTEGER DEFAULT 0 CHECK (time_spent_minutes >= 0),

    -- Timestamps
    enrolled_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_accessed TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMPTZ,

    -- Unique constraint: one enrollment per user per course
    CONSTRAINT unique_user_course_enrollment UNIQUE (user_id, course_id)
);

-- Step 9: Create lesson_progress table
CREATE TABLE lesson_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Progress relationships
    lesson_id UUID NOT NULL REFERENCES course_lessons(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,

    -- Progress details
    completed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    time_spent_minutes INTEGER DEFAULT 0 CHECK (time_spent_minutes >= 0),
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Unique constraint: one progress record per user per lesson
    CONSTRAINT unique_user_lesson_progress UNIQUE (user_id, lesson_id)
);

-- Step 10: Create indexes for efficient querying

-- Courses indexes
CREATE INDEX idx_courses_department_id
ON courses(department_id)
WHERE department_id IS NOT NULL;

CREATE INDEX idx_courses_status
ON courses(status);

CREATE INDEX idx_courses_difficulty
ON courses(difficulty)
WHERE difficulty IS NOT NULL;

CREATE INDEX idx_courses_title
ON courses USING gin(to_tsvector('english', title));

CREATE INDEX idx_courses_created_by
ON courses(created_by);

CREATE INDEX idx_courses_user_id
ON courses(user_id);

CREATE INDEX idx_courses_created_at
ON courses(created_at DESC);

CREATE INDEX idx_courses_not_deleted
ON courses(id)
WHERE is_deleted = FALSE;

CREATE INDEX idx_courses_rating
ON courses(rating DESC)
WHERE rating IS NOT NULL;

-- Array indexes for courses
CREATE INDEX idx_courses_tags
ON courses USING gin(tags);

CREATE INDEX idx_courses_learning_objectives
ON courses USING gin(learning_objectives);

-- Course modules indexes
CREATE INDEX idx_course_modules_course_id
ON course_modules(course_id);

CREATE INDEX idx_course_modules_order
ON course_modules(module_order);

CREATE INDEX idx_course_modules_not_deleted
ON course_modules(id)
WHERE is_deleted = FALSE;

-- Course lessons indexes
CREATE INDEX idx_course_lessons_module_id
ON course_lessons(module_id);

CREATE INDEX idx_course_lessons_order
ON course_lessons(lesson_order);

CREATE INDEX idx_course_lessons_content_type
ON course_lessons(content_type);

CREATE INDEX idx_course_lessons_not_deleted
ON course_lessons(id)
WHERE is_deleted = FALSE;

-- GIN index for lesson resources
CREATE INDEX idx_course_lessons_resources
ON course_lessons USING gin(resources);

-- Course prerequisites indexes
CREATE INDEX idx_course_prerequisites_course_id
ON course_prerequisites(course_id);

CREATE INDEX idx_course_prerequisites_prereq_id
ON course_prerequisites(prerequisite_course_id);

-- Course enrollments indexes
CREATE INDEX idx_course_enrollments_course_id
ON course_enrollments(course_id);

CREATE INDEX idx_course_enrollments_user_id
ON course_enrollments(user_id);

CREATE INDEX idx_course_enrollments_enrolled_at
ON course_enrollments(enrolled_at DESC);

CREATE INDEX idx_course_enrollments_last_accessed
ON course_enrollments(last_accessed DESC);

-- Lesson progress indexes
CREATE INDEX idx_lesson_progress_lesson_id
ON lesson_progress(lesson_id);

CREATE INDEX idx_lesson_progress_user_id
ON lesson_progress(user_id);

CREATE INDEX idx_lesson_progress_completed_at
ON lesson_progress(completed_at DESC);

-- Step 11: Create helper function to enroll user in course
CREATE OR REPLACE FUNCTION enroll_in_course(
    p_course_id UUID,
    p_user_id VARCHAR
)
RETURNS UUID AS $$
DECLARE
    v_enrollment_id UUID;
BEGIN
    -- Check if already enrolled
    SELECT id INTO v_enrollment_id
    FROM course_enrollments
    WHERE course_id = p_course_id
      AND user_id = p_user_id;

    -- Create enrollment if not exists
    IF v_enrollment_id IS NULL THEN
        INSERT INTO course_enrollments (course_id, user_id)
        VALUES (p_course_id, p_user_id)
        RETURNING id INTO v_enrollment_id;

        -- Update enrolled count
        UPDATE courses
        SET enrolled_count = enrolled_count + 1
        WHERE id = p_course_id;
    END IF;

    RETURN v_enrollment_id;
END;
$$ LANGUAGE plpgsql;

-- Step 12: Create helper function to mark lesson as complete
CREATE OR REPLACE FUNCTION complete_lesson(
    p_lesson_id UUID,
    p_user_id VARCHAR,
    p_time_spent_minutes INTEGER DEFAULT 0,
    p_notes TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_module_id UUID;
    v_course_id UUID;
    v_enrollment_id UUID;
    v_completed_lessons INTEGER;
    v_total_lessons INTEGER;
    v_new_progress NUMERIC;
BEGIN
    -- Get module and course IDs
    SELECT module_id INTO v_module_id
    FROM course_lessons
    WHERE id = p_lesson_id;

    SELECT course_id INTO v_course_id
    FROM course_modules
    WHERE id = v_module_id;

    -- Ensure user is enrolled
    SELECT id INTO v_enrollment_id
    FROM course_enrollments
    WHERE course_id = v_course_id
      AND user_id = p_user_id;

    IF v_enrollment_id IS NULL THEN
        RAISE EXCEPTION 'User not enrolled in course';
    END IF;

    -- Insert or update lesson progress
    INSERT INTO lesson_progress (
        lesson_id,
        user_id,
        time_spent_minutes,
        notes
    ) VALUES (
        p_lesson_id,
        p_user_id,
        p_time_spent_minutes,
        p_notes
    )
    ON CONFLICT (user_id, lesson_id)
    DO UPDATE SET
        completed_at = NOW(),
        time_spent_minutes = lesson_progress.time_spent_minutes + EXCLUDED.time_spent_minutes,
        notes = COALESCE(EXCLUDED.notes, lesson_progress.notes);

    -- Calculate new progress
    SELECT COUNT(*) INTO v_completed_lessons
    FROM lesson_progress lp
    INNER JOIN course_lessons cl ON lp.lesson_id = cl.id
    INNER JOIN course_modules cm ON cl.module_id = cm.id
    WHERE cm.course_id = v_course_id
      AND lp.user_id = p_user_id;

    SELECT COUNT(*) INTO v_total_lessons
    FROM course_lessons cl
    INNER JOIN course_modules cm ON cl.module_id = cm.id
    WHERE cm.course_id = v_course_id
      AND cl.is_deleted = FALSE;

    v_new_progress := (v_completed_lessons::NUMERIC / NULLIF(v_total_lessons, 0)) * 100;

    -- Update enrollment progress
    UPDATE course_enrollments
    SET overall_progress = v_new_progress,
        completed_lessons = v_completed_lessons,
        time_spent_minutes = time_spent_minutes + p_time_spent_minutes,
        last_accessed = NOW(),
        completed_at = CASE
            WHEN v_new_progress >= 100 AND completed_at IS NULL THEN NOW()
            ELSE completed_at
        END
    WHERE id = v_enrollment_id;

    -- Return progress data
    RETURN jsonb_build_object(
        'lesson_id', p_lesson_id,
        'completed_at', NOW(),
        'course_progress', v_new_progress
    );
END;
$$ LANGUAGE plpgsql;

-- Step 13: Create function to get course progress
CREATE OR REPLACE FUNCTION get_course_progress(
    p_course_id UUID,
    p_user_id VARCHAR
)
RETURNS TABLE (
    course_id UUID,
    course_title VARCHAR,
    enrolled_at TIMESTAMPTZ,
    last_accessed TIMESTAMPTZ,
    overall_progress NUMERIC,
    completed_lessons INTEGER,
    total_lessons INTEGER,
    time_spent_minutes INTEGER,
    modules_progress JSONB,
    current_lesson JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS course_id,
        c.title AS course_title,
        ce.enrolled_at,
        ce.last_accessed,
        ce.overall_progress,
        ce.completed_lessons,
        c.lesson_count AS total_lessons,
        ce.time_spent_minutes,
        COALESCE(
            jsonb_agg(
                DISTINCT jsonb_build_object(
                    'module_id', cm.id,
                    'module_title', cm.title,
                    'progress', (
                        SELECT COUNT(*)::NUMERIC / NULLIF(cm.lesson_count, 0) * 100
                        FROM lesson_progress lp
                        INNER JOIN course_lessons cl ON lp.lesson_id = cl.id
                        WHERE cl.module_id = cm.id
                          AND lp.user_id = p_user_id
                    ),
                    'completed_lessons', (
                        SELECT COUNT(*)
                        FROM lesson_progress lp
                        INNER JOIN course_lessons cl ON lp.lesson_id = cl.id
                        WHERE cl.module_id = cm.id
                          AND lp.user_id = p_user_id
                    ),
                    'total_lessons', cm.lesson_count
                )
            ) FILTER (WHERE cm.id IS NOT NULL),
            '[]'::jsonb
        ) AS modules_progress,
        (
            SELECT jsonb_build_object(
                'lesson_id', cl.id,
                'title', cl.title,
                'module_title', cm.title
            )
            FROM course_lessons cl
            INNER JOIN course_modules cm ON cl.module_id = cm.id
            LEFT JOIN lesson_progress lp ON cl.id = lp.lesson_id AND lp.user_id = p_user_id
            WHERE cm.course_id = p_course_id
              AND lp.id IS NULL
              AND cl.is_deleted = FALSE
            ORDER BY cm.module_order, cl.lesson_order
            LIMIT 1
        ) AS current_lesson
    FROM courses c
    INNER JOIN course_enrollments ce ON c.id = ce.course_id
    LEFT JOIN course_modules cm ON c.id = cm.course_id AND cm.is_deleted = FALSE
    WHERE c.id = p_course_id
      AND ce.user_id = p_user_id
      AND c.is_deleted = FALSE
    GROUP BY c.id, c.title, ce.enrolled_at, ce.last_accessed, ce.overall_progress, ce.completed_lessons, ce.time_spent_minutes;
END;
$$ LANGUAGE plpgsql;

-- Step 14: Create view for course statistics
CREATE OR REPLACE VIEW course_statistics AS
SELECT
    c.id AS course_id,
    c.title,
    c.status,
    c.difficulty,
    c.department_id,
    c.module_count,
    c.lesson_count,
    c.enrolled_count,
    c.completion_rate,
    c.rating,
    COUNT(ce.id) AS active_enrollments,
    COUNT(ce.id) FILTER (WHERE ce.completed_at IS NOT NULL) AS completed_enrollments,
    AVG(ce.overall_progress)::NUMERIC(4, 2) AS avg_progress,
    SUM(ce.time_spent_minutes)::INTEGER AS total_time_spent_minutes
FROM courses c
LEFT JOIN course_enrollments ce ON c.id = ce.course_id
WHERE c.is_deleted = FALSE
GROUP BY c.id
ORDER BY c.enrolled_count DESC;

-- Step 15: Create view for popular courses
CREATE OR REPLACE VIEW popular_courses AS
SELECT
    c.id AS course_id,
    c.title,
    c.description,
    c.department_id,
    c.difficulty,
    c.estimated_hours,
    c.enrolled_count,
    c.rating,
    c.tags,
    COUNT(ce.id) AS current_enrollments,
    COUNT(ce.id) FILTER (WHERE ce.completed_at IS NOT NULL) AS completions
FROM courses c
LEFT JOIN course_enrollments ce ON c.id = ce.course_id
WHERE c.status = 'published'
  AND c.is_deleted = FALSE
GROUP BY c.id
HAVING COUNT(ce.id) >= 10
ORDER BY c.enrolled_count DESC, c.rating DESC NULLS LAST
LIMIT 50;

-- Step 16: Create trigger to update module counts
CREATE OR REPLACE FUNCTION update_module_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Update course module count
        UPDATE courses
        SET module_count = module_count + 1
        WHERE id = NEW.course_id;
    ELSIF TG_OP = 'DELETE' THEN
        -- Update course module count
        UPDATE courses
        SET module_count = GREATEST(0, module_count - 1)
        WHERE id = OLD.course_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_module_counts
AFTER INSERT OR DELETE ON course_modules
FOR EACH ROW
EXECUTE FUNCTION update_module_counts();

-- Step 17: Create trigger to update lesson counts
CREATE OR REPLACE FUNCTION update_lesson_counts()
RETURNS TRIGGER AS $$
DECLARE
    v_course_id UUID;
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Get course ID
        SELECT course_id INTO v_course_id
        FROM course_modules
        WHERE id = NEW.module_id;

        -- Update module lesson count
        UPDATE course_modules
        SET lesson_count = lesson_count + 1
        WHERE id = NEW.module_id;

        -- Update course lesson count
        UPDATE courses
        SET lesson_count = lesson_count + 1
        WHERE id = v_course_id;

    ELSIF TG_OP = 'DELETE' THEN
        -- Get course ID
        SELECT course_id INTO v_course_id
        FROM course_modules
        WHERE id = OLD.module_id;

        -- Update module lesson count
        UPDATE course_modules
        SET lesson_count = GREATEST(0, lesson_count - 1)
        WHERE id = OLD.module_id;

        -- Update course lesson count
        UPDATE courses
        SET lesson_count = GREATEST(0, lesson_count - 1)
        WHERE id = v_course_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_lesson_counts
AFTER INSERT OR DELETE ON course_lessons
FOR EACH ROW
EXECUTE FUNCTION update_lesson_counts();

-- Step 18: Add comments documenting the schema
COMMENT ON TABLE courses IS
'Educational courses with hierarchical structure: Course → Module → Lesson (v7.3 Feature 6).
Supports CRUD operations, progress tracking, and knowledge base integration.';

COMMENT ON TABLE course_modules IS
'Modules within courses, ordered sequentially with learning objectives (v7.3 Feature 6)';

COMMENT ON TABLE course_lessons IS
'Individual lessons within modules with various content types and resources (v7.3 Feature 6)';

COMMENT ON TABLE course_prerequisites IS
'Many-to-many mapping of course prerequisites for learning path dependencies (v7.3 Feature 6)';

COMMENT ON TABLE course_enrollments IS
'User enrollments in courses with progress tracking and completion status (v7.3 Feature 6)';

COMMENT ON TABLE lesson_progress IS
'Individual lesson completion records for progress tracking (v7.3 Feature 6)';

COMMENT ON COLUMN courses.learning_objectives IS
'Array of learning objective strings for course outcomes';

COMMENT ON COLUMN courses.tags IS
'Array of tags for course categorization and discovery';

COMMENT ON COLUMN course_lessons.resources IS
'Array of supplementary resources: [{"type": "pdf", "title": "...", "url": "..."}]';

COMMENT ON VIEW course_statistics IS
'Aggregate statistics for all courses including enrollments and progress (v7.3 Feature 6)';

COMMENT ON VIEW popular_courses IS
'Top 50 most enrolled and highly rated courses (v7.3 Feature 6)';

COMMENT ON FUNCTION enroll_in_course IS
'Enroll a user in a course and update enrollment count (v7.3 Feature 6)';

COMMENT ON FUNCTION complete_lesson IS
'Mark lesson as complete and update course progress automatically (v7.3 Feature 6)';

COMMENT ON FUNCTION get_course_progress IS
'Retrieve complete progress data for a user in a course (v7.3 Feature 6)';
