FROM ghcr.io/n8n-io/n8n:2.19.5

USER root

COPY docker/entrypoint.sh /entrypoint.sh
COPY workflow-assets /opt/bootstrap/workflow-assets
COPY workflows /opt/bootstrap/workflows

RUN chmod +x /entrypoint.sh \
    && chown -R node:node /entrypoint.sh /opt/bootstrap

USER node

ENTRYPOINT ["/entrypoint.sh"]
