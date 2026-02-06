.PHONY: up down logs nuke init check setup help postgres-start postgres-stop postgres-create-tables postgres-shell postgres-status postgres-nuke
# Colors for terminal output
GREEN := \033[0;32m
YELLOW := \033[0;33m
CYAN := \033[0;36m
NC := \033[0m
init:
	@echo "$(CYAN)Initializing project...$(NC)"
	@mkdir -p ./data/cache
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env file from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(GREEN).env file created!$(NC)"; \
		echo "$(YELLOW)Please review and update credentials in .env file$(NC)"; \
	else \
		echo "$(YELLOW).env file already exists, skipping...$(NC)"; \
	fi
	@echo "$(GREEN)Initialization complete!$(NC)"
check: init
	@echo "$(CYAN)Running pre-flight checks...$(NC)"
	@ERRORS=0; \
	if ! docker info > /dev/null 2>&1; then \
		echo "$(YELLOW)  [FAIL] Docker is not running. Start Docker Desktop and try again.$(NC)"; \
		ERRORS=1; \
	else \
		echo "  [OK] Docker is running"; \
	fi; \
	if [ ! -f .env ]; then \
		echo "$(YELLOW)  [FAIL] .env file not found. Run 'make init' first.$(NC)"; \
		ERRORS=1; \
	else \
		echo "  [OK] .env file exists"; \
		if grep -q "POSTGRES_PASSWORD=xxxx" .env 2>/dev/null; then \
			echo "$(YELLOW)  [FAIL] POSTGRES_PASSWORD is still a placeholder in .env. Update it.$(NC)"; \
			ERRORS=1; \
		fi; \
		if grep -q "AIRFLOW_ADMIN_PASSWORD=xxxxx" .env 2>/dev/null; then \
			echo "$(YELLOW)  [FAIL] AIRFLOW_ADMIN_PASSWORD is still a placeholder in .env. Update it.$(NC)"; \
			ERRORS=1; \
		fi; \
	fi; \
	GCP_CREDS="$$HOME/.config/gcloud/application_default_credentials.json"; \
	if [ ! -f "$$GCP_CREDS" ]; then \
		echo "$(YELLOW)  [FAIL] GCP credentials not found at $$GCP_CREDS$(NC)"; \
		echo "$(YELLOW)         Run 'make setup' to authenticate with GCP.$(NC)"; \
		ERRORS=1; \
	else \
		echo "  [OK] GCP credentials found"; \
	fi; \
	if lsof -i :8080 > /dev/null 2>&1; then \
		echo "$(YELLOW)  [WARN] Port 8080 is in use. Airflow may fail to start.$(NC)"; \
	fi; \
	if lsof -i :5432 > /dev/null 2>&1; then \
		echo "$(YELLOW)  [WARN] Port 5432 is in use. PostgreSQL may fail to start.$(NC)"; \
	fi; \
	if [ $$ERRORS -ne 0 ]; then \
		echo ""; \
		echo "$(YELLOW)Pre-flight checks failed. Fix the issues above and try again.$(NC)"; \
		exit 1; \
	fi; \
	echo "$(GREEN)All pre-flight checks passed!$(NC)"
setup:
	@echo "$(CYAN)Setting up GCP authentication...$(NC)"
	@RESOURCE_TYPE=$$(grep 'resource_type' terraform/environments/dev/config.tfvars | sed 's/.*= *"//;s/"//'); \
	REGION=$$(grep 'region' terraform/environments/dev/config.tfvars | head -1 | sed 's/.*= *"//;s/"//'); \
	PROJECT_ID_BASE=$$(grep 'project_id_base' terraform/environments/dev/config.tfvars | sed 's/.*= *"//;s/"//'); \
	ENVIRONMENT=$$(grep 'environment' terraform/environments/dev/config.tfvars | sed 's/.*= *"//;s/"//'); \
	INSTANCE_NUMBER=$$(grep 'instance_number' terraform/environments/dev/config.tfvars | sed 's/.*= *"//;s/"//'); \
	PROJECT_ID="$${PROJECT_ID_BASE}-$${ENVIRONMENT}-$${INSTANCE_NUMBER}"; \
	BUCKET="$${PROJECT_ID_BASE}-$${ENVIRONMENT}-$${RESOURCE_TYPE}-$${REGION}-$${INSTANCE_NUMBER}"; \
	echo ""; \
	echo "  Project ID: $${PROJECT_ID}"; \
	echo "  Bucket:     gs://$${BUCKET}"; \
	echo "  Auth:       Application Default Credentials (user)"; \
	echo ""; \
	echo "$(YELLOW)Step 1: Generating Application Default Credentials...$(NC)"; \
	gcloud auth application-default login; \
	echo ""; \
	echo "$(YELLOW)Step 2: Granting bucket access to your account...$(NC)"; \
	gcloud storage buckets add-iam-policy-binding \
		"gs://$${BUCKET}" \
		--member="user:$$(gcloud config get account 2>/dev/null)" \
		--role="roles/storage.objectAdmin" \
		--project="$${PROJECT_ID}" || { echo "$(YELLOW)Warning: Could not grant bucket access. You may need to do this manually.$(NC)"; }; \
	echo ""; \
	if [ -f "$$HOME/.config/gcloud/application_default_credentials.json" ]; then \
		echo "$(GREEN)GCP authentication configured successfully!$(NC)"; \
	else \
		echo "$(YELLOW)Warning: Credentials file not found. Authentication may have failed.$(NC)"; \
	fi
up: init check
	@echo "$(CYAN)Starting NYC Taxi ETL services...$(NC)"
	@docker-compose up -d
	@echo ""
	@echo "$(GREEN)Services started successfully!$(NC)"
	@echo ""
	@echo "$(YELLOW)Service URLs:$(NC)"
	@echo "  Airflow UI:     http://localhost:8080"
	@echo ""
	@echo "$(YELLOW)Airflow Credentials:$(NC)"
	@echo "  Username: admin"
	@echo "  Password: admin"
	@echo ""
	@echo "$(CYAN)Showing logs (Ctrl+C to exit):$(NC)"
	@docker-compose logs -f
down:
	@echo "$(CYAN)Stopping NYC Taxi ETL services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)Services stopped$(NC)"
logs:
	@docker-compose logs -f
nuke:
	@echo "$(YELLOW)WARNING: This will remove ALL containers, images, volumes, and data!$(NC)"
	@echo "$(YELLOW)This includes:$(NC)"
	@echo "  - All Docker containers (PostgreSQL, ETL, Airflow)"
	@echo "  - All Docker images (PostgreSQL, Airflow, etc.)"
	@echo "  - All Docker volumes (PostgreSQL data, Airflow logs)"
	@echo "  - All Docker networks"
	@echo "  - All build cache"
	@echo ""
	@echo "$(YELLOW)Press Ctrl+C within 5 seconds to cancel...$(NC)"
	@sleep 5
	@echo ""
	@echo "$(CYAN)Stopping and removing all containers and volumes...$(NC)"
	@docker-compose down -v --remove-orphans
	@echo ""
	@echo "$(CYAN)Removing project Docker images...$(NC)"
	@docker rmi postgres:15-alpine 2>/dev/null || true
	@echo ""
	@echo "$(CYAN)Removing dangling images...$(NC)"
	@docker image prune -af
	@echo ""
	@echo "$(CYAN)Removing all unused volumes...$(NC)"
	@docker volume prune -af
	@echo ""
	@echo "$(CYAN)Removing all unused networks...$(NC)"
	@docker network prune -f
	@echo ""
	@echo "$(CYAN)Removing build cache...$(NC)"
	@docker builder prune -af
	@echo ""
	@echo "$(CYAN)Final system cleanup...$(NC)"
	@docker system prune -af --volumes
	@echo ""
	@echo "$(GREEN)Complete cleanup finished!$(NC)"
	@echo ""
	@echo "$(CYAN)Docker system status:$(NC)"
	@docker system df
postgres-start: init
	@echo "$(CYAN)Starting PostgreSQL...$(NC)"
	@docker-compose up -d bigquery
	@echo ""
	@echo "$(GREEN)PostgreSQL started!$(NC)"
	@echo "$(YELLOW)Connection details:$(NC)"
	@echo "  Host:     localhost"
	@echo "  Port:     5432"
	@echo "  Database: $$(grep POSTGRES_DB .env | cut -d '=' -f2)"
	@echo "  User:     $$(grep POSTGRES_USER .env | cut -d '=' -f2)"
	@echo ""
	@echo "$(CYAN)Waiting for PostgreSQL to be ready...$(NC)"
	@sleep 3
	@docker-compose exec bigquery pg_isready -U postgres || echo "$(YELLOW)PostgreSQL is starting up...$(NC)"
postgres-stop:
	@echo "$(CYAN)Stopping PostgreSQL...$(NC)"
	@docker-compose stop bigquery
	@echo "$(GREEN)PostgreSQL stopped$(NC)"
postgres-nuke: postgres-stop
	@echo "$(RED)⚠️  WARNING: This will destroy all PostgreSQL data!$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to cancel, or Enter to continue...$(NC)"
	@read -r confirm
	@echo "$(CYAN)Removing PostgreSQL container and volumes...$(NC)"
	@docker-compose rm -f bigquery
	@docker volume rm nyc-taxi-etl_postgres_data 2>/dev/null || echo "$(YELLOW)Volume already removed$(NC)"
	@echo "$(GREEN)✓ PostgreSQL completely removed$(NC)"
	@echo ""
	@echo "$(CYAN)Recreating PostgreSQL from scratch...$(NC)"
	@docker-compose up -d bigquery
	@echo "$(CYAN)Waiting for PostgreSQL to initialize and run init scripts...$(NC)"
	@sleep 8
	@until docker-compose exec -T bigquery pg_isready -U postgres > /dev/null 2>&1; do \
		echo "$(YELLOW)  Still initializing...$(NC)"; \
		sleep 2; \
	done
	@echo "$(GREEN)✓ PostgreSQL is ready!$(NC)"
	@echo ""
	@echo "$(CYAN)Verifying database and tables...$(NC)"
	@docker-compose exec -T bigquery psql -U postgres -d nyc_taxi -c "\dt taxi.*" || echo "$(RED)Tables not created yet$(NC)"
	@echo ""
	@echo "$(GREEN)✓ PostgreSQL recreated with fresh schema!$(NC)"
	@echo "$(YELLOW)Schema: taxi$(NC)"
	@echo "$(YELLOW)Tables: dim_date, dim_location, dim_payment, fact_trip$(NC)"
	@echo "$(YELLOW)All indexes and constraints created automatically$(NC)"
postgres-create-tables: postgres-start
	@echo "$(CYAN)Creating PostgreSQL tables...$(NC)"
	@docker-compose exec bigquery psql -U postgres -d nyc_taxi -f /docker-entrypoint-initdb.d/create_dimensional_model.sql
	@echo "$(GREEN)Tables created successfully!$(NC)"
	@echo ""
	@echo "$(YELLOW)Tables created:$(NC)"
	@docker-compose exec bigquery psql -U postgres -d nyc_taxi -c "\dt taxi.*"
postgres-shell:
	@echo "$(CYAN)Connecting to PostgreSQL...$(NC)"
	@docker-compose exec bigquery psql -U postgres -d nyc_taxi
postgres-status:
	@echo "$(CYAN)PostgreSQL Status:$(NC)"
	@docker-compose exec bigquery pg_isready -U postgres && echo "$(GREEN)✓ PostgreSQL is ready$(NC)" || echo "$(YELLOW)✗ PostgreSQL is not ready$(NC)"
	@echo ""
	@echo "$(CYAN)Database Info:$(NC)"
	@docker-compose exec bigquery psql -U postgres -d nyc_taxi -c "SELECT version();" 2>/dev/null || echo "$(YELLOW)Cannot connect to PostgreSQL$(NC)"
	@echo ""
	@echo "$(CYAN)Table Counts:$(NC)"
	@docker-compose exec bigquery psql -U postgres -d nyc_taxi -c "\
		SELECT 'dim_date' as table_name, COUNT(*) as records FROM taxi.dim_date \
		UNION ALL SELECT 'dim_location', COUNT(*) FROM taxi.dim_location \
		UNION ALL SELECT 'dim_payment', COUNT(*) FROM taxi.dim_payment \
		UNION ALL SELECT 'fact_trip', COUNT(*) FROM taxi.fact_trip;" 2>/dev/null || echo "$(YELLOW)Tables not yet created$(NC)"
help:
	@echo "$(CYAN)NYC Taxi ETL - Available Make commands:$(NC)"
	@echo ""
	@echo "$(YELLOW)General:$(NC)"
	@echo "  $(GREEN)make init$(NC)                     - Initialize directories and environment"
	@echo "  $(GREEN)make setup$(NC)                    - Set up GCP authentication (ADC + bucket access)"
	@echo "  $(GREEN)make check$(NC)                    - Run pre-flight checks (Docker, credentials, ports)"
	@echo "  $(GREEN)make up$(NC)                       - Start all services (PostgreSQL + Airflow)"
	@echo "  $(GREEN)make down$(NC)                     - Stop all services"
	@echo "  $(GREEN)make logs$(NC)                     - Show service logs"
	@echo "  $(GREEN)make nuke$(NC)                     - Remove all containers, images, and volumes"
	@echo ""
	@echo "$(YELLOW)PostgreSQL:$(NC)"
	@echo "  $(GREEN)make postgres-start$(NC)           - Start PostgreSQL container"
	@echo "  $(GREEN)make postgres-stop$(NC)            - Stop PostgreSQL container"
	@echo "  $(GREEN)make postgres-create-tables$(NC)   - Create dimensional model tables"
	@echo "  $(GREEN)make postgres-shell$(NC)           - Connect to PostgreSQL shell"
	@echo "  $(GREEN)make postgres-status$(NC)          - Show PostgreSQL status and table counts"
	@echo ""
	@echo "  $(GREEN)make help$(NC)                     - Show this help message"
