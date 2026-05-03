Place RHEL 9 Docker Engine RPMs and dependencies here before creating the bootstrap archive.

Typical staging command on an internet-connected RHEL 9 compatible host:

```bash
dnf download --resolve --destdir deploy/offline-bundle/rpms docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
