create or replace function hybrid_search(
  q_text      text,
  q_emb       vector(1024),
  pid         uuid,
  match_count int default 8
)
returns table (id uuid, section text, content text, score float)
language sql stable as $$
with vec as (
  select id, section, content,
         row_number() over (order by embedding <=> q_emb) as rnk
  from record_chunks
  where patient_id = pid
  order by embedding <=> q_emb
  limit 30
),
lex as (
  select id, section, content,
         row_number() over (
           order by ts_rank(content_tsv, plainto_tsquery('english', q_text)) desc
         ) as rnk
  from record_chunks
  where patient_id = pid
    and content_tsv @@ plainto_tsquery('english', q_text)
  limit 30
)
select
  coalesce(v.id, l.id),
  coalesce(v.section, l.section),
  coalesce(v.content, l.content),
  coalesce(1.0/(60 + v.rnk), 0) + coalesce(1.0/(60 + l.rnk), 0) as score
from vec v
full outer join lex l on v.id = l.id
order by score desc
limit match_count;
$$;
