# Toram Utils

Streamlit skill-tree simulator for Toram skill data.

## Structure

```text
.
├── app.py                         # Streamlit entrypoint wrapper
├── toram_utils/
│   ├── paths.py                   # Shared project paths
│   ├── core/                      # Pure skill-tree domain logic
│   ├── data/                      # JSON/raw text loading and lookup
│   └── ui/                        # Streamlit state, events, controls, docs
├── components/skill_graph/        # Custom Streamlit graph component
├── doc/
│   ├── skill_restriction/         # Normalized skill-tree restriction JSON
│   ├── coryn_skills/              # Crawled Coryn skill detail JSON
│   └── raw_skills/                # Cleaned raw skill text
├── raw_source/raw_skills/         # Original raw skill text inputs
├── assets/skill_tree/             # Skill icon assets
└── tests/
```

## Architecture

`toram_utils.core` contains immutable models and skill-tree rules: validation, traversal, unlock checks, allocation, refunding, and import/export validation.

`toram_utils.data` owns file loading and normalization-specific lookup code for restriction JSON, raw skill text, and Coryn detail JSON.

`toram_utils.ui` owns Streamlit session state, graph event handling, controls, build management, and raw skill documentation rendering.

The root `app.py` only calls `toram_utils.ui.streamlit_app.main()` so `streamlit run app.py` remains stable.

## Data Conventions

Each file in `doc/skill_restriction` uses the same top-level keys:

```json
{
  "skill_tree": "Blade",
  "tree_slug": "blade",
  "group": "weapon_class_skills",
  "raw_skill_file": "weapon_class_skills/blade_skills.txt",
  "coordinate_system": {},
  "skills": []
}
```

Each skill entry uses:

```json
{
  "id": "hard_hit",
  "name": "Hard Hit",
  "position": [3, 0],
  "prerequisites": []
}
```

Icon paths are resolved as `assets/skill_tree/{tree_slug}/{skill_id}.png`.

## Run On Windows PowerShell

```powershell
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
streamlit run app.py
```

## Testing

```powershell
pytest
```

## Supabase Auth And Storage

Saved builds and preferences use Supabase when these Streamlit secrets are configured:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

Create these tables in Supabase:

```sql
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text,
  preferences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table saved_builds (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text not null default '',
  build jsonb not null,
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, name)
);
```

Enable Row Level Security:

```sql
alter table profiles enable row level security;
alter table saved_builds enable row level security;

create policy "Users can read own profile"
on profiles for select using (auth.uid() = id);

create policy "Users can insert own profile"
on profiles for insert with check (auth.uid() = id);

create policy "Users can update own profile"
on profiles for update using (auth.uid() = id) with check (auth.uid() = id);

create policy "Users can read own builds"
on saved_builds for select using (auth.uid() = user_id);

create policy "Users can insert own builds"
on saved_builds for insert with check (auth.uid() = user_id);

create policy "Users can update own builds"
on saved_builds for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users can delete own builds"
on saved_builds for delete using (auth.uid() = user_id);
```

If Supabase secrets are missing, app login/save is disabled. The storage layer still has a local `data/saved_builds.json` fallback for local scripts/tests.

## Build Save And Share

Use saved builds for local work and share links for chat.

Full build JSON includes the build name, description, levels, and UI settings:

```json
{
  "version": 1,
  "name": "Blade DPS",
  "description": "Shared DPS setup for guild review.",
  "build": {
    "version": 1,
    "levels": {
      "hammer_slam": 5,
      "cleaving_attack": 2
    }
  },
  "settings": {
    "total_points": 427,
    "tree_order": [],
    "collapsed_trees": {}
  }
}
```

The app still accepts the older raw build JSON format:

```json
{
  "version": 1,
  "levels": {
    "hammer_slam": 5
  }
}
```

Sharing options:

1. Save the build in the `Saved builds` form to keep its name and description during the current session.
2. Click `Share current build` to copy a URL with the compressed build data to your clipboard.
3. Send the copied link through Discord/chat.

Skill definitions stay in `doc/skill_restriction`; exports only contain player allocation and build metadata.
