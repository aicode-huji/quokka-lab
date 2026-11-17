# Ollama for the CPU only: the official image's program and CPU libraries on a
# plain Ubuntu, without the GPU libraries the lab never uses (CUDA 12, CUDA 13,
# MLX for CUDA, Vulkan: about 4.4 GB). Same Ollama release as the official
# image. Measured on amd64: a 61 MB download, 233 MB on disk, against 3.4 GB
# and 8.5 GB for ollama/ollama:0.40.16, with the same CPU backend and speed.
#
# Published as ghcr.io/aicode-huji/quokka-ollama-cpu by
# .github/workflows/ollama-image.yml (amd64 and arm64). docker-compose.yml
# pulls it. If the pull fails, build it by hand (downloads the full official
# image, 3.4 GB):
#   docker build -t ghcr.io/aicode-huji/quokka-ollama-cpu:0.40.16 ollama

# The official release, pinned by digest (multi-arch).
FROM ollama/ollama:0.40.16@sha256:910d0d8107b538fb0894e63163eb195de0cc7aefcbc666dc62d3b18f71124592 AS official
# Keep everything in /usr/lib/ollama except the GPU backends and C headers.
RUN mkdir -p /out/usr/lib/ollama /out/usr/bin \
    && cp -a /usr/bin/ollama /out/usr/bin/ \
    && cd /usr/lib/ollama \
    && for f in *; do \
         case "$f" in cuda_*|mlx_*|rocm*|vulkan|include) ;; \
                      *) cp -a "$f" /out/usr/lib/ollama/ ;; esac; \
       done

# The official image's own base, Ubuntu 24.04, pinned by digest (multi-arch).
# The program and its CPU libraries need only the C/C++ runtime that Ubuntu
# has; ca-certificates lets `ollama pull` download the model over HTTPS.
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=official /out/ /
ENV OLLAMA_HOST=0.0.0.0:11434
EXPOSE 11434
ENTRYPOINT ["/usr/bin/ollama"]
CMD ["serve"]
