# Meta Model API notes

Sources: https://dev.meta.ai/docs/{pricing-rate-limits,tool-calling,structured-output,image-understanding,speech-to-text} and /docs/api-reference/voice/{transcribe,schemas}, fetched 2026-11-01.
Legend: **[VERBATIM]** = example copied from the docs. **[DOC-SHAPE]** = condensed from documented shapes; the field names come from the docs but the exact sample text does not.

## Basics
- Base URL: `https://api.meta.ai/v1`. The API is OpenAI-compatible, so the OpenAI SDK works with `base_url="https://api.meta.ai/v1"` and `api_key=$MODEL_API_KEY`.
- Headers: `Authorization: Bearer $MODEL_API_KEY`, `Content-Type: application/json`
- Endpoints: `POST /v1/chat/completions` and `POST /v1/responses` (the image docs recommend Responses). Speech-to-text uses `POST /v1/asr/transcribe`.

## Models, pricing, rate limits (per team, not per key)
| Model ID | RPM | TPM | Price per 1M tokens (cached / in / out) |
|---|---|---|---|
| `muse-wonder-1.0` | 3,000 | 4M | $0.20 / $4.00 / $20.00 |
| `muse-spark-1.3` (also 1.2, 1.1) | 3,000 | 4M | $0.15 / $1.25 / $4.25 |
| `muse-spark-1.3-contributor`, `-1.2-contributor` | 150 | 3M | $0.002 / $0.10 / $0.20 |
| `sam-3.1` | 3,000 | – | $2.50 per 1k images; $0.20 per 1k video frames (min 50 frames) |
| `muse-image-1.0` | 150 | – | $0.01 per image |
| `muse-voice-transcribe-1.0` | – | – | $0.18 per audio hour; 256 concurrent streams, 16,000 streams per hour |

- Web search grounding costs $2.50 per 1k queries. Requests with `background: true` are capped at 600 per minute per team.
- The pricing page does not list context windows.

## Tool calling (Chat Completions) [DOC-SHAPE]
```json
{
  "model": "muse-spark-1.3",
  "messages": [{"role": "user", "content": "What is the weather in Seattle?"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Return current weather for the given location.",
      "parameters": {
        "type": "object",
        "properties": {"location": {"type": "string", "description": "City name"}},
        "required": ["location"]
      }
    }
  }]
}
```
- Use `tools`, not the deprecated `functions` / `function_call` fields.
- **`tool_choice` must be `"auto"` (the default). Any other value returns HTTP 400.** You cannot force a specific tool.
- Response: `finish_reason: "tool_calls"`, `message.content` is null or empty, and `message.tool_calls[] = {id, type:"function", function:{name, arguments}}`. **`arguments` is a JSON string**, so parse it.
- To return results, append the **full assistant message including `tool_calls`** (omitting it returns HTTP 400), then append one message per call: `{"role":"tool","tool_call_id":"call_abc123","content":"<string result>"}`, then send the request again.
- Responses API equivalent: the output contains `function_call` items `{name, arguments, call_id}`. Reply with an input item `{"type":"function_call_output","call_id":...,"output":...}` and pass `previous_response_id`.

## Structured output [DOC-SHAPE]
Chat Completions uses `response_format`. The Responses API uses `text.format` instead, and `response_format` is ignored there.
```json
{
  "model": "muse-spark-1.3",
  "messages": [
    {"role": "system", "content": "Extract the address into the specified JSON format."},
    {"role": "user", "content": "Format this address: 1 Hacker Wy Menlo Park CA 94025"}
  ],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "Address",
      "strict": false,
      "schema": {
        "type": "object",
        "properties": {
          "street": {"type": "string"}, "city": {"type": "string"},
          "state": {"type": "string"}, "zip": {"type": "string"}
        },
        "required": ["street", "city", "state", "zip"]
      }
    }
  }
}
```
- The result is a JSON **string** in `choices[0].message.content`, so call `JSON.parse` on it. With the Python SDK, `client.beta.chat.completions.parse(response_format=PydanticModel)` returns `.message.parsed`.
- Output is always constrained to the schema. `strict` (default `false`) only adds server-side validation of the schema itself.
- `strict: true` rules: the root must be a plain object (no top-level anyOf/oneOf/allOf/enum/not); `allOf` and `oneOf` are not allowed anywhere; `anyOf` is allowed below the root; every object needs `additionalProperties: false`; `required` must list every property.
- Limits: recursive `$ref` returns 400; nesting depth 10; 5,000 properties; 120k characters of names and enums; 1,000 enum values; more than 200k nodes after inlining is rejected.

## Image input
Chat Completions [VERBATIM shape]:
```json
{
  "model": "muse-spark-1.3",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Describe what you see in this image."},
      {"type": "image_url", "image_url": {"url": "https://... or data:image/jpeg;base64,<b64>"}}
    ]
  }]
}
```
Responses API [VERBATIM shape]:
```json
{
  "model": "muse-spark-1.3",
  "input": [{
    "type": "message", "role": "user",
    "content": [
      {"type": "input_text", "text": "What is in this image?"},
      {"type": "input_image", "image_url": "https://... or data:image/jpeg;base64,<b64>"}
    ]
  }]
}
```
- Images are allowed only in `user` messages. In the Responses API, `input_image` can use `file_id` instead, and `input_file` handles files and PDFs (via `file_id` or `file_url`).
- Limits: inline image up to 50 MB; Files API up to 1 GiB; at most 50 images per request (more returns 400); only the first 50 pages of a PDF are kept.
- MIME types: jpeg, jpg, png, gif, webp, x-icon. An image that cannot be decoded returns 400 `invalid_request_error`.

## Speech-to-text: `POST https://api.meta.ai/v1/asr/transcribe` [VERBATIM]
```bash
curl -X POST "https://api.meta.ai/v1/asr/transcribe?sessionId=optional-id" \
  -H "Authorization: Bearer $MODEL_API_KEY" \
  -H "Accept: application/json" \
  -F 'request={"model":"muse-voice-transcribe-1.0","audioEncoding":"WAV","mode":"PUSH_TO_TALK"};type=application/json' \
  -F "audio=@recording.wav;type=audio/wav"
```
Multipart parts:
- `request` (a JSON part with `type=application/json`):
  - `model` (required): `"muse-voice-transcribe-1.0"`
  - `audioEncoding` (required): `"WAV"`
  - `mode`: `PUSH_TO_TALK` (default) | `ENDPOINTING` | `DIARIZATION`
  - `keywords`: string[]
  - `languageBias`: string[] such as `["English"]`
  - `partialMode`: `CUMULATIVE` | `DELTA`. Applies to SSE responses only.
  - `emitAudioProgress`: bool. Applies to SSE responses only.
- `audio`: a RIFF/WAVE file, **mono, 16-bit PCM, 16 kHz or 24 kHz**. Convert other formats first: `ffmpeg -i in.m4a -ac 1 -ar 24000 -c:a pcm_s16le -map_metadata -1 out.wav`
- Query parameter `sessionId` is optional; the server generates one if omitted.
- `Accept` header: `application/json` (default, buffered), `text/event-stream` (SSE), or `text/plain`. Anything else returns 406.
- Limits: 32 MB body (413 if exceeded), 10 minutes of audio (400 if exceeded). 429 means rate or concurrency limited, so back off. 500 means retry once.

Response (`TranscribeResponse`):
```json
{
  "sessionId": "string",
  "transcript": "full text",
  "audioDurationMs": 12345,
  "turns": [{"turnId": 0, "startMs": 0, "endMs": 1800, "transcript": "...", "speaker": "A"}]
}
```
`turns` is empty in `PUSH_TO_TALK` mode. `speaker` appears only in `DIARIZATION` mode.

Browser note [INFERRED]: MediaRecorder produces webm/opus, which this endpoint rejects. Either convert the audio to 16 kHz mono PCM WAV on the client (Web Audio API) or run ffmpeg on the server before uploading.
