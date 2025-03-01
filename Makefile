.PHONY: docker docker-runtime-certification runtime-certification-workers

docker:
	@docker compose -f docker-compose.yaml up

docker-runtime-certification:
	@docker compose -f docker-compose.yaml -f docker-compose.certification.yaml --profile runtime-certification up

runtime-certification-workers:
	@export RUNTIME_VERIFICATION_CONFIG="configs/runtime-verification.yaml" && \
	poetry run dramatiq agent_contracts.certification.workers

