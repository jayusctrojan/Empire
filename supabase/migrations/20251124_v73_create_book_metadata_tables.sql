-- Empire v7.3 - Migration 2.6: Create Book Metadata Tables
-- Task: Create tables for book processing with chapter detection (Feature 8)
--
-- Feature 8: Book Processing with Automatic Chapter Detection
-- Goal: Support PDF/EPUB/MOBI books with >90% accurate chapter detection
-- Target: Per-chapter knowledge base indexing with table of contents extraction

-- Step 1: Create file_format enum for book formats
CREATE TYPE file_format AS ENUM (
    'pdf',
    'epub',
    'mobi'
);

-- Step 2: Create book_processing_status enum
CREATE TYPE book_processing_status AS ENUM (
    'processing',
    'complete',
    'failed'
);

-- Step 3: Create chapter_detection_mode enum
CREATE TYPE chapter_detection_mode AS ENUM (
    'auto',
    'strict',
    'relaxed'
);

-- Step 4: Create book_authors table (for many-to-many relationship)
CREATE TABLE book_authors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Author information
    name VARCHAR(200) NOT NULL,
    normalized_name VARCHAR(200) NOT NULL, -- Lowercase, trimmed for matching
    bio TEXT,

    -- Metadata
    country VARCHAR(100),
    birth_year INTEGER,

    -- Tracking
    book_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Ensure unique normalized names
    CONSTRAINT unique_normalized_author_name UNIQUE (normalized_name)
);

-- Step 5: Create publishers table (optional, for future expansion)
CREATE TABLE publishers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Publisher information
    name VARCHAR(200) NOT NULL,
    normalized_name VARCHAR(200) NOT NULL,

    -- Metadata
    country VARCHAR(100),
    founded_year INTEGER,
    website VARCHAR(500),

    -- Tracking
    book_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    CONSTRAINT unique_normalized_publisher_name UNIQUE (normalized_name)
);

-- Step 6: Create books table
CREATE TABLE books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Book identification
    title VARCHAR(500) NOT NULL,
    isbn VARCHAR(13), -- ISBN-10 or ISBN-13 (stored as 13-digit format)

    -- Relationships
    document_id VARCHAR(255) REFERENCES documents_v2(document_id) ON DELETE CASCADE,
    author_id UUID REFERENCES book_authors(id) ON DELETE SET NULL,
    publisher_id UUID REFERENCES publishers(id) ON DELETE SET NULL,
    department_id INTEGER CHECK (department_id >= 1 AND department_id <= 12),

    -- Book metadata
    publication_year INTEGER CHECK (publication_year >= 1000 AND publication_year <= 9999),
    genre VARCHAR(100),
    language VARCHAR(10), -- ISO 639-1 code (e.g., 'en', 'es')
    edition VARCHAR(100),

    -- File information
    file_type file_format NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes > 0),
    file_url TEXT NOT NULL,

    -- Content statistics
    page_count INTEGER CHECK (page_count > 0),
    word_count INTEGER CHECK (word_count >= 0),
    chapter_count INTEGER DEFAULT 0 CHECK (chapter_count >= 0),

    -- Processing configuration
    processing_options JSONB DEFAULT '{}'::jsonb,
    -- Structure: {
    --   "detect_chapters": true,
    --   "extract_toc": true,
    --   "chapter_detection_mode": "auto",
    --   "create_full_book_index": true
    -- }

    -- Table of contents (auto-extracted)
    table_of_contents JSONB DEFAULT '[]'::jsonb,
    -- Structure: [
    --   {
    --     "chapter": 1,
    --     "title": "Introduction",
    --     "page": 1,
    --     "subsections": [
    --       {"title": "Overview", "page": 3},
    --       {"title": "Objectives", "page": 5}
    --     ]
    --   }
    -- ]

    -- Processing status
    processing_status book_processing_status DEFAULT 'processing' NOT NULL,
    processing_error TEXT,

    -- Timestamps
    uploaded_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- User tracking
    user_id VARCHAR(255) NOT NULL,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Step 7: Create book_chapters table
CREATE TABLE book_chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Book relationship
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,

    -- Chapter identification
    chapter_number INTEGER NOT NULL CHECK (chapter_number >= 1),
    title VARCHAR(500) NOT NULL,

    -- Page range
    page_start INTEGER NOT NULL CHECK (page_start >= 1),
    page_end INTEGER NOT NULL CHECK (page_end >= page_start),

    -- Content statistics
    word_count INTEGER CHECK (word_count >= 0),

    -- AI-generated summaries and metadata
    summary TEXT,
    key_topics TEXT[], -- Array of main topics covered

    -- Subsections within chapter
    subsections JSONB DEFAULT '[]'::jsonb,
    -- Structure: [
    --   {"title": "Background", "page_range": [3, 7]},
    --   {"title": "Methodology", "page_range": [8, 15]}
    -- ]

    -- Chapter detection metadata
    detection_confidence NUMERIC(3, 2) CHECK (detection_confidence >= 0 AND detection_confidence <= 1),
    detection_method VARCHAR(50), -- 'regex', 'ml', 'toc_extraction', 'manual'

    -- Embedding and indexing
    has_embeddings BOOLEAN DEFAULT FALSE,
    embeddings_count INTEGER DEFAULT 0,
    indexed_at TIMESTAMPTZ,

    -- Hierarchy (for nested chapters/sections)
    parent_chapter_id UUID REFERENCES book_chapters(id) ON DELETE CASCADE,
    depth INTEGER DEFAULT 1 CHECK (depth >= 1),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Unique constraint for chapter numbers within a book
    CONSTRAINT unique_book_chapter_number UNIQUE (book_id, chapter_number)
);

-- Step 8: Create book_author_mapping table (many-to-many)
CREATE TABLE book_author_mapping (
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES book_authors(id) ON DELETE CASCADE,
    author_order INTEGER DEFAULT 1, -- For multiple authors
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    PRIMARY KEY (book_id, author_id)
);

-- Step 9: Create indexes for efficient querying

-- Books indexes
CREATE INDEX idx_books_document_id
ON books(document_id)
WHERE document_id IS NOT NULL;

CREATE INDEX idx_books_isbn
ON books(isbn)
WHERE isbn IS NOT NULL;

CREATE INDEX idx_books_title
ON books USING gin(to_tsvector('english', title));

CREATE INDEX idx_books_author_id
ON books(author_id)
WHERE author_id IS NOT NULL;

CREATE INDEX idx_books_publisher_id
ON books(publisher_id)
WHERE publisher_id IS NOT NULL;

CREATE INDEX idx_books_genre
ON books(genre)
WHERE genre IS NOT NULL;

CREATE INDEX idx_books_processing_status
ON books(processing_status);

CREATE INDEX idx_books_user_id
ON books(user_id);

CREATE INDEX idx_books_uploaded_at
ON books(uploaded_at DESC);

CREATE INDEX idx_books_department_id
ON books(department_id)
WHERE department_id IS NOT NULL;

CREATE INDEX idx_books_not_deleted
ON books(id)
WHERE is_deleted = FALSE;

-- GIN indexes for JSONB columns
CREATE INDEX idx_books_toc
ON books USING gin(table_of_contents);

CREATE INDEX idx_books_processing_options
ON books USING gin(processing_options);

-- Book chapters indexes
CREATE INDEX idx_book_chapters_book_id
ON book_chapters(book_id);

CREATE INDEX idx_book_chapters_chapter_number
ON book_chapters(chapter_number);

CREATE INDEX idx_book_chapters_title
ON book_chapters USING gin(to_tsvector('english', title));

CREATE INDEX idx_book_chapters_has_embeddings
ON book_chapters(has_embeddings)
WHERE has_embeddings = TRUE;

CREATE INDEX idx_book_chapters_parent
ON book_chapters(parent_chapter_id)
WHERE parent_chapter_id IS NOT NULL;

CREATE INDEX idx_book_chapters_page_range
ON book_chapters(page_start, page_end);

-- GIN index for subsections
CREATE INDEX idx_book_chapters_subsections
ON book_chapters USING gin(subsections);

-- Array index for key topics
CREATE INDEX idx_book_chapters_key_topics
ON book_chapters USING gin(key_topics);

-- Book authors indexes
CREATE INDEX idx_book_authors_name
ON book_authors USING gin(to_tsvector('english', name));

CREATE INDEX idx_book_authors_normalized_name
ON book_authors(normalized_name);

-- Publishers indexes
CREATE INDEX idx_publishers_normalized_name
ON publishers(normalized_name);

-- Book author mapping indexes
CREATE INDEX idx_book_author_mapping_author_id
ON book_author_mapping(author_id);

CREATE INDEX idx_book_author_mapping_book_id
ON book_author_mapping(book_id);

-- Step 10: Create helper function to add or get author
CREATE OR REPLACE FUNCTION get_or_create_author(
    p_author_name VARCHAR
)
RETURNS UUID AS $$
DECLARE
    v_author_id UUID;
    v_normalized_name VARCHAR;
BEGIN
    -- Normalize author name
    v_normalized_name := LOWER(TRIM(p_author_name));

    -- Try to find existing author
    SELECT id INTO v_author_id
    FROM book_authors
    WHERE normalized_name = v_normalized_name;

    -- Create new author if not found
    IF v_author_id IS NULL THEN
        INSERT INTO book_authors (name, normalized_name)
        VALUES (p_author_name, v_normalized_name)
        RETURNING id INTO v_author_id;
    END IF;

    RETURN v_author_id;
END;
$$ LANGUAGE plpgsql;

-- Step 11: Create helper function to add or get publisher
CREATE OR REPLACE FUNCTION get_or_create_publisher(
    p_publisher_name VARCHAR
)
RETURNS UUID AS $$
DECLARE
    v_publisher_id UUID;
    v_normalized_name VARCHAR;
BEGIN
    -- Normalize publisher name
    v_normalized_name := LOWER(TRIM(p_publisher_name));

    -- Try to find existing publisher
    SELECT id INTO v_publisher_id
    FROM publishers
    WHERE normalized_name = v_normalized_name;

    -- Create new publisher if not found
    IF v_publisher_id IS NULL THEN
        INSERT INTO publishers (name, normalized_name)
        VALUES (p_publisher_name, v_normalized_name)
        RETURNING id INTO v_publisher_id;
    END IF;

    RETURN v_publisher_id;
END;
$$ LANGUAGE plpgsql;

-- Step 12: Create function to add chapter to book
CREATE OR REPLACE FUNCTION add_book_chapter(
    p_book_id UUID,
    p_chapter_number INTEGER,
    p_title VARCHAR,
    p_page_start INTEGER,
    p_page_end INTEGER,
    p_detection_confidence NUMERIC DEFAULT NULL,
    p_detection_method VARCHAR DEFAULT 'auto'
)
RETURNS UUID AS $$
DECLARE
    v_chapter_id UUID;
BEGIN
    INSERT INTO book_chapters (
        book_id,
        chapter_number,
        title,
        page_start,
        page_end,
        detection_confidence,
        detection_method
    ) VALUES (
        p_book_id,
        p_chapter_number,
        p_title,
        p_page_start,
        p_page_end,
        p_detection_confidence,
        p_detection_method
    )
    RETURNING id INTO v_chapter_id;

    -- Update chapter count in books table
    UPDATE books
    SET chapter_count = (
        SELECT COUNT(*)
        FROM book_chapters
        WHERE book_id = p_book_id
    )
    WHERE id = p_book_id;

    RETURN v_chapter_id;
END;
$$ LANGUAGE plpgsql;

-- Step 13: Create function to get book with chapters
CREATE OR REPLACE FUNCTION get_book_with_chapters(
    p_book_id UUID
)
RETURNS TABLE (
    book_id UUID,
    title VARCHAR,
    author_name VARCHAR,
    isbn VARCHAR,
    publication_year INTEGER,
    genre VARCHAR,
    language VARCHAR,
    file_type file_format,
    file_size_bytes BIGINT,
    page_count INTEGER,
    word_count INTEGER,
    chapter_count INTEGER,
    chapters JSONB,
    table_of_contents JSONB,
    processing_status book_processing_status,
    uploaded_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.id AS book_id,
        b.title,
        ba.name AS author_name,
        b.isbn,
        b.publication_year,
        b.genre,
        b.language,
        b.file_type,
        b.file_size_bytes,
        b.page_count,
        b.word_count,
        b.chapter_count,
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'chapter_id', bc.id,
                    'chapter_number', bc.chapter_number,
                    'title', bc.title,
                    'page_range', jsonb_build_array(bc.page_start, bc.page_end),
                    'word_count', bc.word_count,
                    'has_embeddings', bc.has_embeddings
                )
                ORDER BY bc.chapter_number
            ) FILTER (WHERE bc.id IS NOT NULL),
            '[]'::jsonb
        ) AS chapters,
        b.table_of_contents,
        b.processing_status,
        b.uploaded_at,
        b.processed_at
    FROM books b
    LEFT JOIN book_authors ba ON b.author_id = ba.id
    LEFT JOIN book_chapters bc ON b.id = bc.book_id AND bc.parent_chapter_id IS NULL
    WHERE b.id = p_book_id
      AND b.is_deleted = FALSE
    GROUP BY b.id, ba.name;
END;
$$ LANGUAGE plpgsql;

-- Step 14: Create view for books with complete metadata
CREATE OR REPLACE VIEW books_with_metadata AS
SELECT
    b.id AS book_id,
    b.title,
    ba.name AS author_name,
    p.name AS publisher_name,
    b.isbn,
    b.publication_year,
    b.genre,
    b.language,
    b.file_type,
    b.file_size_bytes,
    b.page_count,
    b.word_count,
    b.chapter_count,
    b.processing_status,
    COUNT(bc.id) AS indexed_chapters,
    COUNT(bc.id) FILTER (WHERE bc.has_embeddings = TRUE) AS chapters_with_embeddings,
    b.uploaded_at,
    b.processed_at
FROM books b
LEFT JOIN book_authors ba ON b.author_id = ba.id
LEFT JOIN publishers p ON b.publisher_id = p.id
LEFT JOIN book_chapters bc ON b.id = bc.book_id
WHERE b.is_deleted = FALSE
GROUP BY b.id, ba.name, p.name
ORDER BY b.uploaded_at DESC;

-- Step 15: Create view for chapter analytics
CREATE OR REPLACE VIEW book_chapter_analytics AS
SELECT
    b.id AS book_id,
    b.title AS book_title,
    COUNT(bc.id) AS total_chapters,
    AVG(bc.page_end - bc.page_start + 1)::INTEGER AS avg_chapter_pages,
    AVG(bc.word_count)::INTEGER AS avg_chapter_words,
    AVG(bc.detection_confidence)::NUMERIC(3, 2) AS avg_detection_confidence,
    COUNT(*) FILTER (WHERE bc.has_embeddings = TRUE) AS chapters_indexed,
    COUNT(*) FILTER (WHERE bc.detection_method = 'regex') AS regex_detected,
    COUNT(*) FILTER (WHERE bc.detection_method = 'ml') AS ml_detected,
    COUNT(*) FILTER (WHERE bc.detection_method = 'toc_extraction') AS toc_extracted,
    MIN(bc.created_at) AS first_chapter_created,
    MAX(bc.indexed_at) AS last_chapter_indexed
FROM books b
INNER JOIN book_chapters bc ON b.id = bc.book_id
WHERE b.is_deleted = FALSE
GROUP BY b.id, b.title;

-- Step 16: Create trigger to update author book count
CREATE OR REPLACE FUNCTION update_author_book_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE book_authors
        SET book_count = book_count + 1
        WHERE id = NEW.author_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE book_authors
        SET book_count = book_count - 1
        WHERE id = OLD.author_id;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' AND NEW.author_id != OLD.author_id THEN
        UPDATE book_authors
        SET book_count = book_count - 1
        WHERE id = OLD.author_id;

        UPDATE book_authors
        SET book_count = book_count + 1
        WHERE id = NEW.author_id;
        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_author_book_count
AFTER INSERT OR UPDATE OR DELETE ON book_author_mapping
FOR EACH ROW
EXECUTE FUNCTION update_author_book_count();

-- Step 17: Create trigger to update publisher book count
CREATE OR REPLACE FUNCTION update_publisher_book_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.publisher_id IS NOT NULL THEN
        UPDATE publishers
        SET book_count = book_count + 1
        WHERE id = NEW.publisher_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' AND OLD.publisher_id IS NOT NULL THEN
        UPDATE publishers
        SET book_count = book_count - 1
        WHERE id = OLD.publisher_id;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' AND NEW.publisher_id != OLD.publisher_id THEN
        IF OLD.publisher_id IS NOT NULL THEN
            UPDATE publishers
            SET book_count = book_count - 1
            WHERE id = OLD.publisher_id;
        END IF;

        IF NEW.publisher_id IS NOT NULL THEN
            UPDATE publishers
            SET book_count = book_count + 1
            WHERE id = NEW.publisher_id;
        END IF;
        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_publisher_book_count
AFTER INSERT OR UPDATE OR DELETE ON books
FOR EACH ROW
EXECUTE FUNCTION update_publisher_book_count();

-- Step 18: Add comments documenting the schema
COMMENT ON TABLE books IS
'Books uploaded for processing with automatic chapter detection (v7.3 Feature 8).
Supports PDF, EPUB, MOBI formats with >90% chapter detection accuracy.';

COMMENT ON TABLE book_chapters IS
'Individual chapters within books with page ranges, embeddings, and subsections (v7.3 Feature 8).
Auto-detected using regex patterns, ML algorithms, and TOC extraction.';

COMMENT ON TABLE book_authors IS
'Authors of books with normalized names for deduplication (v7.3 Feature 8)';

COMMENT ON TABLE publishers IS
'Publishers of books with normalized names for deduplication (v7.3 Feature 8)';

COMMENT ON TABLE book_author_mapping IS
'Many-to-many mapping between books and authors (v7.3 Feature 8)';

COMMENT ON COLUMN books.table_of_contents IS
'Auto-extracted table of contents with chapter hierarchy and subsections';

COMMENT ON COLUMN books.processing_options IS
'Processing configuration: chapter detection mode, TOC extraction, full-book indexing';

COMMENT ON COLUMN book_chapters.detection_confidence IS
'Confidence score (0-1) for chapter detection accuracy';

COMMENT ON COLUMN book_chapters.detection_method IS
'Method used for chapter detection: regex, ml, toc_extraction, or manual';

COMMENT ON COLUMN book_chapters.subsections IS
'Array of subsections within chapter with page ranges: [{"title": "...", "page_range": [x, y]}]';

COMMENT ON VIEW books_with_metadata IS
'Books with author, publisher, and chapter indexing statistics (v7.3 Feature 8)';

COMMENT ON VIEW book_chapter_analytics IS
'Analytics on chapter detection accuracy and indexing progress (v7.3 Feature 8)';

COMMENT ON FUNCTION get_or_create_author IS
'Get existing author or create new one with normalized name matching (v7.3 Feature 8)';

COMMENT ON FUNCTION get_or_create_publisher IS
'Get existing publisher or create new one with normalized name matching (v7.3 Feature 8)';

COMMENT ON FUNCTION add_book_chapter IS
'Add a chapter to a book and update chapter count (v7.3 Feature 8)';

COMMENT ON FUNCTION get_book_with_chapters IS
'Retrieve complete book details with all chapters in JSON format (v7.3 Feature 8)';
