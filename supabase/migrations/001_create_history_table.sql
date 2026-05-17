-- Create analysis_history table for Truth_X
CREATE TABLE IF NOT EXISTS analysis_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Task metadata
  task_type VARCHAR(50) NOT NULL CHECK (task_type IN (
    'Intel Verification',
    'Video Analysis',
    'Fake News Check',
    'Image Analysis',
    'URL Verification',
    'Text Analysis',
    'AI Detection'
  )),
  
  -- Content summary (concise)
  input_summary TEXT NOT NULL, -- e.g., "YouTube URL", "headline preview", "first 100 chars"
  
  -- Results
  verdict_label VARCHAR(50), -- e.g., "Supported", "Contradicted", "AI Generated", "Likely Real", "Partially Supported", "Unverified"
  verdict_score INTEGER, -- 0-100 credibility score
  
  -- Processing metadata
  processing_time_ms INTEGER, -- milliseconds
  processing_time_formatted VARCHAR(20), -- e.g., "4.2s", "1m 02s"
  
  -- Intelligence data
  evidence_count INTEGER DEFAULT 0,
  source_count INTEGER DEFAULT 0,
  summary TEXT, -- brief intelligence summary
  
  -- Optional extended metadata (stored as JSONB for flexibility)
  metadata JSONB, -- can store model_used, additional_fields, etc.
  
  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  -- Indexes for fast queries
  CONSTRAINT user_history_idx UNIQUE (user_id, id)
);

-- Create index on user_id for fast queries
CREATE INDEX analysis_history_user_id_idx ON analysis_history(user_id);
CREATE INDEX analysis_history_created_at_idx ON analysis_history(user_id, created_at DESC);
CREATE INDEX analysis_history_task_type_idx ON analysis_history(task_type);

-- Enable Row Level Security
ALTER TABLE analysis_history ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own history
CREATE POLICY "Users can view their own history"
  ON analysis_history
  FOR SELECT
  USING (auth.uid() = user_id);

-- RLS Policy: Users can only insert their own history
CREATE POLICY "Users can insert their own history"
  ON analysis_history
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- RLS Policy: Users can only update their own history
CREATE POLICY "Users can update their own history"
  ON analysis_history
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- RLS Policy: Users can only delete their own history
CREATE POLICY "Users can delete their own history"
  ON analysis_history
  FOR DELETE
  USING (auth.uid() = user_id);

-- Grant permissions
GRANT ALL ON analysis_history TO authenticated;
GRANT USAGE ON SCHEMA public TO authenticated;
