# Dataset Quality Report

Input: `data\dataset.csv`
Clean output: `data\dataset_clean.csv`
Retrieval output: `data\dataset_retrieval.csv`

## Summary

- Original chunks: 1136
- Recommended retrieval chunks: 1127
- Excluded chunks: 9
- Sources: 6
- Categories filled: 1136/1136
- Articles filled: 387/1136
- Sections filled: 99/1136

## What Changed

- Filled the empty `category` column from source-file mapping.
- Added stable `chunk_id` values for auditing and deduplication.
- Added `document_type`, `year`, `is_table`, `prefix_context`, `topic_tags`, `char_count`, `word_count`, `quality_flags`, and `include_for_retrieval`.
- Flagged low-quality chunks such as short title pages, very short chunks, over-long chunks, and low-information table rows.
- Produced a retrieval-only CSV that excludes chunks likely to hurt retrieval precision.
- Added an optional CSV loader for the ingest pipeline via `DATASET_CSV`.

## Chunks By Category

| category | chunks |
|---|---:|
| Công tác sinh viên | 396 |
| Sổ tay sinh viên | 277 |
| Ngoại ngữ | 179 |
| Quy chế đào tạo | 155 |
| Tuyển sinh | 74 |
| Học phí | 55 |

## Quality Flags

| flag | chunks |
|---|---:|
|  | 1092 |
| too_short | 41 |
| title_or_cover_page | 5 |
| too_long | 2 |
| low_information_table | 1 |

## Topic Tags

| topic | chunks |
|---|---:|
| dao_tao | 553 |
| ngoai_ngu | 289 |
| dia_diem | 287 |
|  | 280 |
| tuyen_sinh | 108 |
| hoc_phi | 85 |
| lien_he | 64 |
| hoc_bong | 43 |
| ky_tuc_xa | 17 |
| ehust | 10 |

## Recommendation

Use `dataset_clean.csv` as the canonical audited corpus. Use `dataset_retrieval.csv` when rebuilding the vector database, because it removes low-information table rows, title-only pages, and short chunks without useful contact signals.

Rebuild Chroma from the cleaned retrieval corpus with:

```powershell
cd backend
$env:DATASET_CSV='../data/dataset_retrieval.csv'
python -m ingest.pipeline
```
