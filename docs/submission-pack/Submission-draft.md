# DecisionDesk — submission draft

Status: prepared for review, not submitted. Team/member/contact details, final recording URL and judge access remain for the user to provide. This draft does not assert that all competition requirements have been fulfilled.

## Product

**DecisionDesk — meeting memory that leads to reviewed action**

**Problem selected:** Product Space Problem 3, meeting-to-execution.

**Target user and problem:** Small project teams need to remember what they agreed, recognize when that agreement changes, and know who owns each next step. A standalone meeting summary does not itself resolve contradictory decisions or create accountable follow-through.

**Solution:** DecisionDesk accepts speaker-labelled meeting text, including input dictated through Wispr Flow. Local AI proposes decisions, tasks, named owners and deadlines with source evidence. It compares proposals with accepted memory and asks the user to resolve changed decisions. Only reviewed plans update memory. GitHub issue creation has a separate destination-specific preview and confirmation step. Local task tracking, due-date views and per-person weekly digests support follow-through.

**Distinctive mechanism:** A decision is compared across meetings and explicitly accepted or rejected, with superseded values retained in history. Demonstrate this mechanism with two clearly fictional meetings rather than claiming novelty over every existing product.

**Architecture:** Streamlit UI; SQLite workspace storage; local Ollama/Qwen3 1.7B inference; source-grounding checks; GitHub CLI adapter for explicitly approved issue creation. No paid AI API is used. The app is localhost-only and has not been cloud-deployed.

**Supporting features:** Searchable meeting memory, cited AI questions and drafts, task dependencies/priorities, calendar export, separate workspaces, validated backup/restore and a live meeting notes companion. The live companion has an agenda and resumable timer; it does not host or record calls. Live sessions have a separate notes export.

## Validation and limits

- 79 automated checks passed before submission preparation. Tests cover extraction/provider boundaries, SQLite workflows, approvals/conflicts, tracker mocks, workspace features, assistant source checks, live sessions and navigation.
- Local AI extraction and all six assistant tools have been exercised with fictional inputs. These are functional checks, not real-world accuracy or productivity benchmarks.
- The final two-meeting live-AI rehearsal passed, including a spoken correction, conflict rejection/resolution, completion, digest, history and backup restore. See Rehearsal-results.md.
- GitHub creation is implemented, mock-tested, and now live-verified with one explicitly user-approved fictional issue: https://github.com/devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31/issues/1. Its title/body match the preview (normalizing GitHub line endings), and the app records the task as published.
- Exact-quote validation checks provenance; it does not prove an AI interpretation is correct. Owners, dates, suggested steps and decisions require review.
- In-app reminders run while using the app. No background email or attendee messaging is implemented.
- Localhost cannot be opened remotely by judges. Supply an accessible recording and suitable source-code access without publishing the application.
- Wispr Flow usage is reported by the user. Genuine development and product-input evidence still needs to be captured and reviewed; no automated typed rehearsal is voice evidence.
- No measured adoption, time saved, customer accuracy or engagement outcome is claimed.

## Contribution disclosure

The generic development environment and launcher were prepared before kickoff. DecisionDesk implementation began after kickoff at the user's request. The user selected the problem and directed product decisions, design references and iteration. Codex generated substantial application code, tests, fictional examples and documentation. Wispr Flow contribution should describe the exact real prompts and product inputs actually dictated, backed by the recorded evidence; do not claim that all code was voice-written.

## Links to complete before submission

- Final demo video: not supplied yet.
- Genuine Wispr evidence clip(s): not supplied yet.
- Private source repository: https://github.com/devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31
- Judge code access: not verified; do not assume judges can access a private repository.
- Live tracker demonstration issue URL: https://github.com/devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31/issues/1 (one fictional issue, created with explicit user approval).
- Team name and primary-member contact details: user to complete in the authenticated form.

Previously recorded project portal: https://theproductspace.in/user-dashboard/submissions/agentic-ai-hackathons
Previously recorded deadline: **31 October 2026, 11:59 PM IST**.
Previously recorded LinkedIn portal: https://theproductspace.in/user-dashboard/linkedin-submissions/agentic-ai-hackathons
Previously recorded LinkedIn deadline: **1 November 2026, 11:59 PM IST**.

Check the latest organizer announcement and authenticated portal before relying on these saved requirements. Public pages were unavailable to the final web check. Nothing has been uploaded, shared with judges or submitted by the assistant.
