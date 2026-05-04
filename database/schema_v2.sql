-- Update daily_shots table to include current_affairs column
ALTER TABLE public.daily_shots 
ADD COLUMN IF NOT EXISTS current_affairs TEXT;

-- Alternatively, if daily_shots doesn't exist at all yet:
CREATE TABLE IF NOT EXISTS public.daily_shots (
    id SERIAL PRIMARY KEY,
    lesson_date DATE UNIQUE NOT NULL,
    vocab TEXT,
    idiom TEXT,
    gk_fact TEXT,
    current_affairs TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Users table update (if needed, although it should be fine as it's from V1/V2)
CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    displayname TEXT,
    role TEXT DEFAULT 'LEARNER',
    streak INT DEFAULT 0,
    last_correct_date DATE,
    last_active_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
