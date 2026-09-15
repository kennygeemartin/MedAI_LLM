# Free model and hosting assessment

Checked 15 September 2026 against the publishers' documentation.

## Selected route

The user declined Hugging Face. Use GPT-OSS 20B through the existing Groq Free
account, with no new account or paid compute. This is a general pretrained
model, not a medical specialist. The options below document the research;
Hugging Face deployment is not being pursued.

## Finding

Free pretrained medical models exist. Training from scratch is unnecessary for
this project and would not resolve hosted API usage limits. Model weights,
training compute, and hosting compute are separate resources.

The production logs for the reported headache fallback show Groq returned
HTTP 429 at 01:25:33 local time. The preceding request succeeded. The app was
mislabeling provider failure as missing reviewed evidence. This is not evidence
that the model has no knowledge of headaches.

## Models

| Candidate | Access and terms | Assessment for MedAI |
| --- | --- | --- |
| [Google MedGemma 4B IT](https://huggingface.co/google/medgemma-4b-it) | Downloadable after accepting Google's Health AI Developer Foundations terms | First medical-specific candidate to evaluate; existing GPU service already targets it. It still needs task-specific evaluation. |
| [BioMistral 7B](https://huggingface.co/BioMistral/BioMistral-7B) | Apache 2.0 weights | Research comparator. Authors explicitly advise against production health use because clinical performance is unvalidated. |
| [OpenBioLLM 8B](https://huggingface.co/aaditya/Llama3-OpenBioLLM-8B) | Downloadable under Llama 3 terms | Another medical research comparator. Its model card is not proof of suitability for autonomous patient care. |
| [Qwen 3.6 27B on Groq](https://console.groq.com/docs/model/qwen/qwen3.6-27b) | General model available through a quota-limited Free plan | Previous model; supported prototype dialogue. It is not a medical-specific model, and API availability is not continuous under free quotas. |

| [GPT-OSS 20B](https://developers.openai.com/api/docs/models/gpt-oss-20b) | Apache 2.0 open weights; hosted on Groq Free | Selected replacement, requiring no Hugging Face account. General education only, subject to the same account usage limits. |

## Hosting without payment

### Hugging Face ZeroGPU: conditional free MedGemma demo

The [current ZeroGPU documentation](https://huggingface.co/docs/hub/spaces-zerogpu)
says verified personal accounts older than 30 days and in good standing can host
up to two ZeroGPU Spaces free. The published Free-account quota is five minutes
of GPU time per day, with shared queues. Eligibility and remaining quota must be
confirmed on the actual account before promising deployment.

ZeroGPU requires Gradio and GPU-decorated functions. The existing FastAPI Docker
service cannot be uploaded unchanged. The deployment needs a Gradio wrapper,
model loading at module scope, bounded generation under `spaces.GPU`, and a
Vercel adapter for the Gradio API. It also needs accepted model access, account
authentication, private request authorization, queue/time-out handling, and a
real generation test. Never use someone else's public demo as an unapproved
backend or circumvent per-account quotas.

This is suitable for a limited research demonstration, not an assurance of
always-on service for multiple patients. No Space or paid GPU has been created.

### Groq Free

[Published limits](https://console.groq.com/docs/rate-limits) for the selected
model include 30 requests/minute, 1,000 requests/day, 8,000 tokens/minute and
200,000 tokens/day. Account limits can differ and apply across the organization.
Free-plan use must remain within those limits; do not add paid upgrades.
Requests use low reasoning effort, shorten recent context and cap output
at 1,000 tokens to reduce consumption. This reduces usage, not eliminates limits.

### Existing local or university hardware

A downloadable model can run on hardware already available to the project.
This avoids a GPU rental bill but still requires suitable memory, electricity,
network access and uptime. Quantization may reduce memory at the cost of quality
or speed. No local performance or available GPU has been established here.

### Colab

[Colab's FAQ](https://research.google.com/colaboratory/faq.html) describes free
but unguaranteed GPU resources and restrictions on using free runtimes as web
services. Use it for interactive experiments or fine-tuning, not a permanent
backend for this website.

## If later fine-tuning is justified

Evaluate a pretrained baseline first. If it misses the desired conversational
behavior, fine-tune an adapter (LoRA/QLoRA) rather than pretraining a model from
scratch. This does not remove the need for hosting compute.

- [MedQuAD](https://github.com/abachaa/MedQuAD): NIH-derived consumer health QA;
  dataset is CC BY 4.0. Three subsets omit answers for copyright reasons. Keep
  attribution, exclude unavailable answers, and review age and applicability.
- [PubMedQA](https://github.com/pubmedqa/pubmedqa): biomedical research questions
  with yes/no/maybe answers. Useful as one evaluation component; insufficient
  alone to teach patient-facing symptom conversations.

Use deduplicated source-level train/validation/test splits. Include reviewed
examples of clarifying questions, uncertain symptoms, emergency escalation and
appropriate self-care. Evaluate factuality, harmful recommendations, missed
emergencies, inappropriate refusals, Nigerian context, latency and failure
behavior with held-out questions and qualified reviewers. A trained adapter is
not itself evidence of clinical utility. No training or validation is claimed.
