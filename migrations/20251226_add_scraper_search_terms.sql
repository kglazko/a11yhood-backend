-- Migration: Add scraper_search_terms table and RLS policies
-- Date: 2025-12-26

-- Create table to persist scraper search terms per platform
create table if not exists public.scraper_search_terms (
  id bigint generated always as identity primary key,
  platform text not null unique,
  search_terms jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Enable Row Level Security
alter table public.scraper_search_terms enable row level security;

-- Read policy for authenticated users (and service role)
drop policy if exists scraper_terms_select_authenticated on public.scraper_search_terms;
create policy scraper_terms_select_authenticated
  on public.scraper_search_terms
  for select
  using (auth.role() = 'authenticated' or auth.role() = 'service_role');

-- Write policy restricted to service role
drop policy if exists scraper_terms_write_service_role on public.scraper_search_terms;
create policy scraper_terms_write_service_role
  on public.scraper_search_terms
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- Trigger to auto-update updated_at on change
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_scraper_search_terms_updated_at on public.scraper_search_terms;
create trigger set_scraper_search_terms_updated_at
  before update on public.scraper_search_terms
  for each row
  execute function public.set_updated_at();

-- Seed an initial row for github platform if none exists
insert into public.scraper_search_terms (platform, search_terms)
select 'github', '[]'::jsonb
where not exists (
  select 1 from public.scraper_search_terms where platform = 'github'
);

-- Seed Thingiverse and Ravelry defaults if missing
insert into public.scraper_search_terms (platform, search_terms)
select 'thingiverse', '[]'::jsonb
where not exists (
  select 1 from public.scraper_search_terms where platform = 'thingiverse'
);

insert into public.scraper_search_terms (platform, search_terms)
select 'ravelry_pa_categories', '[]'::jsonb
where not exists (
  select 1 from public.scraper_search_terms where platform = 'ravelry_pa_categories'
);
