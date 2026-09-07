# Alquist Insight Prompts

This file defines the LLM prompts used by the RAG pipeline of a single project. This copy is the **default** prompts
file - it is used by every project that does not have its own prompts file.

Upload a customized copy of this file for a project to override the prompts for that project:

```
POST /resources/prompts/?project_id=<project_id>
```

The uploaded file is validated before it is stored, so an invalid file is rejected with an error describing the problem.

## How to edit this file

- Each prompt is defined by a level-2 heading (`## <prompt_name>`) holding the prompt name, followed by a fenced code
  block (```` ``` ````) with the prompt itself.
- **Everything outside the fenced code blocks is ignored** - use the surrounding space freely for comments, notes and
  guidelines like these.
- Do not rename, remove or add prompt headings - the file has to define exactly the prompts listed below, otherwise it
  is rejected as invalid.
- The prompts are templates: a name in curly braces (e.g. `{language}`) is a **variable** that is filled in during
  runtime. Each prompt has to use exactly the variables listed in its section - no more, no less.
- If you need a literal curly brace in a prompt, double it: `{{` and `}}`.
- Keep the instructions short, specific and non-contradictory. Rules that conflict with each other make the answers
  unpredictable.
- After changing a prompt, always test the chatbot on a few real questions - prompt changes affect the quality of every
  answer the project produces. A change becomes effective for new chat sessions immediately (cached for 1 hour for
  existing sessions).

## rag

The main prompt of the RAG pipeline. It is used as the system prompt of the call that generates the answer to the user's
question from the documents retrieved from the knowledge base.

Available variables:

- `{context}` - the retrieved knowledge base documents (chunks) the answer has to be based on
- `{language}` - English name of the conversation language (e.g. `English`, `Czech`)

Guidelines:

- Put the `{context}` variable at the end of the prompt and keep it clearly separated from the instructions (the
  `<CONTEXT>` tags below), so that the model cannot confuse documents with rules.
- Always keep an instruction to answer only from the context and to admit not knowing the answer. Removing it makes the
  chatbot invent facts.
- This is the right place for project-specific instructions, e.g. the role the chatbot should play, the topics it should
  refuse to discuss or the required style/format of the answers.

```text
Use the knowledge base context to answer the user's question.
Always answer in {language}, unless specifically prompted otherwise.
Ground your answer strictly in the provided knowledge base context.
If the answer is not present in that context, say you don't know - do not invent facts.
Be extremely precise. Do not include links or references; put the information directly in the answer.
If there are multiple valid procedures/paths, list them with clear descriptions.
Use the conversation history (if provided) only to resolve references.
Do not copy facts from the history unless they also appear in the retrieved context.

KNOWLEDGE BASE CONTEXT (authoritative): <CONTEXT>
{context}
</CONTEXT>
```

## query_rewrite

The prompt used to rewrite a follow-up question into a standalone search query before the knowledge base is searched. It
is used as the system prompt of the rewrite call, which receives the conversation history and the latest user question.
It runs only when there is a conversation history.

Available variables:

- `{language}` - English name of the conversation language (e.g. `English`, `Czech`)

Guidelines:

- The output of this call is used as a search query, not shown to the user. Always instruct the model to output the
  query only, without any explanation, quotes or formatting.
- Keep the rewrite conservative - the query has to keep the meaning of the original question and only resolve what the
  question refers to in the conversation.

```text
You will receive a conversation history and the user's latest question.
Rewrite ONLY the latest question into a single standalone query that is fully self-contained, resolving pronouns, ellipsis, and references using the conversation.
Output ONLY the rewritten query text, nothing else. Write the query in {language}.
```
