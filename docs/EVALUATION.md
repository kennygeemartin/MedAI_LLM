# Research evaluation plan

## Software verification

Run the API suite and JavaScript syntax check in the README. Then run the deployment smoke checks against a separate test database. Test PostgreSQL, the Vercel deployment, and the GPU service independently; local SQLite success is not evidence that those external environments are working.

## Clinical and retrieval evaluation

Build a versioned, de-identified question set reviewed by qualified healthcare professionals. Cover primary healthcare topics in the intended Nigerian setting, follow-up questions, unclear symptoms, local phrasing, out-of-scope requests, and emergencies. Include questions with no evidence and attempts to obtain prescriptions or override system rules.

For each question, record expected supporting document IDs and expected disposition (education, insufficient evidence, or urgent referral). Have reviewers score retrieved passages, factual support, clarity, and appropriateness. Measure retrieval recall at five passages, unsupported claims, missed urgent referrals, false emergency flags, and source accuracy. Calibrate the semantic-search threshold on a development split; report results on an untouched holdout split.

Compare library-only excerpts against RAG plus MedGemma. Measure multi-turn context performance, latency, model service failures, and output-filter false positives. Do not treat fluent writing or a correct citation URL as proof that the answer is medically correct.

## Known gaps to address before patient use

- Emergency keyword matching has no reliable negation, spelling, multilingual, or temporal understanding.
- Output checks detect some diagnosis and dosage language; they cannot guarantee safe generations.
- Approved documents can become outdated; this version has no automatic expiry or second-reviewer requirement.
- The evidence fallback is lexical and can retrieve irrelevant passages sharing common words.
- Prompts can reduce but cannot eliminate prompt injection or unsupported model claims.
- Document approval records do not validate a reviewer's clinical credentials.
- Establish informed consent, retention, account support, access review, and backup handling with the deployment operator.

Document the model version, corpus snapshot, prompt, embedding model, thresholds, and review protocol alongside any reported research results. No clinical accuracy results have been claimed for this implementation.
