Copy the prepared `.ollama` model store into this folder on a connected staging host before building `loomin-docs-ollama:offline`.

The model blobs and manifests are baked into the exported `loomin-docs-ollama.tar` image because the air-gapped VM cannot run `ollama pull`.
