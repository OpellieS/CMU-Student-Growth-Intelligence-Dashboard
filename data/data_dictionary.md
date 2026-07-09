# Data Dictionary

Processed tables are written to `data/processed/` by `python -m src.clean`.

| Table | Field | Definition |
|---|---|---|
| `current_faculty.csv` | `current_students` | Active students by faculty from `/stat/s001/001`. |
| `current_faculty.csv` | `international_program_share` | International-program students divided by current students. This is a program-format proxy, not nationality. |
| `undergraduate_programs.csv` | `current_students` | Current undergraduate and below students by faculty/program from `/stat/s001/004`. |
| `graduate_programs.csv` | `current_students` | Current graduate students by faculty/program/admission-year view from `/stat/s001/007`. |
| `admission_funnel.csv` | `issued_total` | Students issued CMU student IDs from `/stat/s002/001` or `/stat/s002/002`. |
| `admission_funnel.csv` | `waived_total` | Students who waived/surrendered admission rights. |
| `admission_funnel.csv` | `remaining_total` | Issued-ID students remaining after waivers; treated as realized intake. |
| `admission_funnel.csv` | `waive_rate` | `waived_total / issued_total`. |
| `admission_funnel.csv` | `yield_rate` | `remaining_total / issued_total`. |
| `graduates.csv` | `graduate_count` | Graduated students from `/stat/s003/001`, `/stat/s003/002`, and `/stat/s003/003`. |
| `historical_students.csv` | `student_count` | Historical student count by faculty, academic year, and semester from `/stat/s004/001`. |
| `nationality.csv` | `is_international` | True for non-Thai and non-administrative nationality codes. |
| `over_program_students.csv` | `over_program_rate` | `over_program_students / current_students` from `/stat/s001/010`. |
| `transfer_students.csv` | `net_transfer` | `transfer_in - transfer_out` from `/stat/s001/017`. |
| `all_stats_long.csv` | `total_count` | Best-effort row total, usually the highest `cN` column in the API payload. |
