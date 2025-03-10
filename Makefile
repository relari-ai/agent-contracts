.PHONY: docker docker-runtime-certification workers-runtime-certification stop

docker-verification:
	@docker compose -f docker-compose.yaml up -d

docker-runtime-certification:
	@docker compose -f docker-compose.yaml -f docker-compose.certification.yaml --profile runtime-certification up -d && \
	make workers-runtime-certification

workers-runtime-certification:
	poetry run dramatiq agent_contracts.certification.workers

stop:
	@docker compose -f docker-compose.yaml -f docker-compose.certification.yaml --profile runtime-certification stop 
