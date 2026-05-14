-- Update daily_shots table to include current_affairs column
ALTER TABLE public.daily_shots 
ADD COLUMN IF NOT EXISTS current_affairs TEXT;

-- Update users table to include xp and missing quiz-related columns
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS xp INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS streak INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_correct_date DATE;

-- Create xp_history table
CREATE TABLE IF NOT EXISTS public.xp_history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id),
    amount INTEGER NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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
