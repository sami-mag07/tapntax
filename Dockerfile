# Standard library only, so the image is the interpreter plus this folder.
FROM python:3.12-slim
WORKDIR /app
COPY tapntax ./tapntax
COPY README.md LICENSE ./
ENV PORT=8080 TAPNTAX_STATE=/data
VOLUME /data
EXPOSE 8080
CMD ["sh", "-c", "python3 -m tapntax.server ${PORT}"]
