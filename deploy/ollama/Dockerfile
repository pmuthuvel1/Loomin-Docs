FROM ollama/ollama:offline-base

COPY offline-bundle/ollama-models/ /root/.ollama/
COPY Modelfile.llama3 /opt/loomin/Modelfile.llama3
COPY Modelfile.mistral /opt/loomin/Modelfile.mistral
COPY ollama/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENV OLLAMA_HOST=0.0.0.0:11434
EXPOSE 11434
ENTRYPOINT ["/entrypoint.sh"]
