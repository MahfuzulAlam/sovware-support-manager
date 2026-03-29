-- Supabase database schema snapshot for SovWare Support Manager
-- This file is for reference only (do not run migrations from here).

CREATE TABLE public.agents (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  helpscout_user_id text UNIQUE,
  display_name text NOT NULL,
  email text NOT NULL,
  active boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT agents_pkey PRIMARY KEY (id)
);

CREATE TABLE public.ai_customer_reply (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id text NOT NULL,
  summary text NOT NULL,
  urgency text DEFAULT 'Medium'::text CHECK (urgency = ANY (ARRAY['Low'::text, 'Medium'::text, 'High'::text])),
  category text,
  next_action text,
  model text DEFAULT 'gpt-4'::text,
  created_at timestamp with time zone DEFAULT now(),
  thread_id text,
  cost real,
  emotion text,
  emotion_intensity smallint,
  expectation_gap text,
  revenue_risk text,
  blame_target text,
  strategic_signal text,
  effort_level smallint,
  refund_intent boolean,
  has_query boolean,
  CONSTRAINT ai_customer_reply_pkey PRIMARY KEY (id),
  CONSTRAINT ai_custom_reply_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id)
);

CREATE TABLE public.ai_evaluations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id text NOT NULL,
  summary text NOT NULL,
  urgency text DEFAULT 'Medium'::text CHECK (urgency = ANY (ARRAY['Low'::text, 'Medium'::text, 'High'::text])),
  category text,
  next_action text,
  model text DEFAULT 'gpt-4'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT ai_evaluations_pkey PRIMARY KEY (id),
  CONSTRAINT ai_evaluations_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id)
);

CREATE TABLE public.assignment_rules (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  days_of_week ARRAY DEFAULT ARRAY[0, 1, 2, 3, 4, 5, 6],
  start_time time without time zone NOT NULL DEFAULT '00:00:00'::time without time zone,
  end_time time without time zone NOT NULL DEFAULT '23:59:59'::time without time zone,
  timezone text DEFAULT 'Asia/Dhaka'::text,
  mailbox_id text,
  assign_agent_id uuid,
  priority integer DEFAULT 0,
  enabled boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT assignment_rules_pkey PRIMARY KEY (id),
  CONSTRAINT assignment_rules_assign_agent_id_fkey FOREIGN KEY (assign_agent_id) REFERENCES public.agents(id)
);

CREATE TABLE public.conversation_threads (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id text NOT NULL,
  message_type text NOT NULL CHECK (message_type = ANY (ARRAY['customer'::text, 'agent'::text, 'note'::text])),
  body text NOT NULL,
  created_by text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT conversation_threads_pkey PRIMARY KEY (id),
  CONSTRAINT conversation_threads_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id)
);

CREATE TABLE public.conversations (
  id text NOT NULL,
  mailbox_id text,
  subject text NOT NULL,
  customer_name text,
  customer_email text,
  status text DEFAULT 'active'::text CHECK (status = ANY (ARRAY['active'::text, 'pending'::text, 'closed'::text])),
  assigned_agent_id uuid,
  last_updated_at timestamp with time zone DEFAULT now(),
  raw_payload jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT conversations_pkey PRIMARY KEY (id),
  CONSTRAINT conversations_assigned_agent_id_fkey FOREIGN KEY (assigned_agent_id) REFERENCES public.agents(id)
);

CREATE TABLE public.doc_suggestions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id text NOT NULL,
  title text NOT NULL,
  missing text NOT NULL,
  outline text,
  placement text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT doc_suggestions_pkey PRIMARY KEY (id),
  CONSTRAINT doc_suggestions_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id)
);

CREATE TABLE public.events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  conversation_id text,
  payload jsonb NOT NULL,
  processed boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT events_pkey PRIMARY KEY (id)
);

CREATE TABLE public.feature_requests (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id text NOT NULL,
  title text NOT NULL,
  problem text NOT NULL,
  impact text,
  solution text,
  priority text DEFAULT 'Medium'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT feature_requests_pkey PRIMARY KEY (id),
  CONSTRAINT feature_requests_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id)
);

CREATE TABLE public.profiles (
  id uuid NOT NULL,
  name text NOT NULL,
  role text NOT NULL DEFAULT 'agent'::text CHECK (role = ANY (ARRAY['admin'::text, 'agent'::text])),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

CREATE TABLE public.secrets (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  key_name text NOT NULL UNIQUE,
  key_value_encrypted text NOT NULL,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT secrets_pkey PRIMARY KEY (id)
);

