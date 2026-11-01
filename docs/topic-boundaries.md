# Topic boundary: learning effects versus classroom practice

## Rule supported by prior human labels

Use the whole article's central question, not the presence of words such as teacher, student, learning, or classroom.

- **T001 — AI adoption and learning effects:** patterns of student use; consequences for learning, critical thinking, skills, and behavior; educational inequality; tutoring outcomes; curriculum-centered institutional adoption.
- **T003 — Classroom implementation and teacher practice:** concrete teaching decisions, assignment and assessment design, classroom implementation, and educators' accounts of teaching with or responding to AI.

A survey about how many students use AI can be T001 even if it mentions teachers changing assignments. An educator's account of designing and assessing classroom work can be T003 even if it discusses effects on student learning. Merely quoting a teacher does not establish T003. Academic-integrity reporting, policy announcements, and literacy resources must still be assessed against T004, T002, and T005 respectively.

## Anchors from existing user labels

| Article | Existing label | Boundary interpretation |
|---|---|---|
| 5134 | T003 | Teacher's first-person account of entering the classroom, choosing assignments, monitoring drafts, and responding to students' AI use. Learning effects occur within the teaching narrative. |
| 5226 | T001 | Discussion of university learning, critical thinking, and widespread AI essay use. |
| 5131 | T001 | Commentary on what universities want students to demonstrate as AI changes learning. |
| 5132 | T001 | Broad concern about AI's effects on student learning and critical thinking, despite examples of professors' responses. |
| 5147 | T003 | Concrete implementation of an AI-powered school's teaching model, despite claims about learning outcomes. |

These are interpretations of existing labels, not new human adjudications. Original labels are unchanged.

## Experimental boundary veto

The neighbor rescue uses opening-text embeddings. A separate binary logistic classifier compares T001 with T003 using verified full-article embeddings and the existing labels. Every evaluated text group is excluded from its training, and duplicate reference text groups receive one vote. It only checks proposed T001/T003 rescues; it cannot replace existing named assignments or change a proposal to the opposing topic.

The proposal is withheld unless the binary classifier agrees with it and the difference between its two probability outputs is at least 0.10. These outputs are uncalibrated. **The margin was selected after inspecting development examples**, including the known error; this is development tuning and not an independent validation result. The binary classifier's default winner alone still gets article 5134 wrong. The improvement comes from abstaining on its narrow result, not from reliably recognizing the teacher-practice theme.

The optional check remains inactive in production. Run it using `neighbor_rescue --boundary-cache review/topic-candidate-v4-full-context` alongside the original cache, baseline, and a new output directory. It needs local review caches, not API keys.

## Development result

| Measure on the 62 reviewed examples | Active | Original rescue | With boundary veto |
|---|---:|---:|---:|
| Correct matches | 24 | 28 | 28 |
| Human-topic articles left Unassigned | 22 | 17 | 18 |
| Added correct assignments | 0 | 4 | 4 |
| Added wrong-topic assignments | 0 | 1 | 0 |
| Correct among all named assignments | 56.8% | 59.5% | 61.0% |

The four retained proposals are 5233 → T004, 5245 → T004, 5226 → T001, and 5131 → T001. Article 5134 remains Unassigned instead of receiving the wrong rescue. This abstention does not fix that article's missed assignment. The active agent's two existing false assignments among the five human-Unassigned articles remain.

Before activation, freeze the policy and assess new articles without exposing predictions during labeling. Assistant-only judgments must be identified separately from human validation. The local per-case output is `review/neighbor-rescue-boundary-v1/evaluation.json`.
