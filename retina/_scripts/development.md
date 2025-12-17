# Develop Retina

Create virtual environment with all necessary packages:

```bash
rm -Rf .venv && python3 -m venv .venv && .venv/bin/pip install -e protocol/ -e client/ -e viavi/ -e agent/ -e orchestrator/ -e launcher/ grpcio-tools black isort pylint mypy mypy-protobuf tox
source .venv/bin/activate
```

## Validation

```bash
cd protocol     && python3 -m tox -r && cd .. && \
cd viavi        && python3 -m tox -r && cd .. && \
cd agent        && python3 -m tox -r && cd .. && \
cd client       && python3 -m tox -r && cd .. && \
cd orchestrator && python3 -m tox -r && cd .. && \
cd launcher     && python3 -m tox -r && cd ..
```

## Autogenerate files

### Protocol

To autogenerate protocol files go to the protocol/ folder and run

```bash
tox -re grpc
```
