# Yelp — Lab 2

Lab 2 extends the Lab 1 monolith into a container-native, event-driven
stack:

- **Docker + Kubernetes** — each service has its own Dockerfile; k8s
  manifests deploy the whole stack.
- **Kafka** — review and restaurant write paths flow through Kafka
  (producer API → topic → worker consumer).
- **MongoDB** — replaces MySQL; sessions stored server-side with a TTL
  index; passwords hashed with bcrypt.
- **Redux Toolkit** — replaces the Lab 1 `AuthContext`; slices for
  `auth`, `restaurants`, `reviews`, `favourites`.
- **JMeter** — `jmeter/yelp-load-test.jmx` parameterised for 100–500
  concurrent users.

See `docs/architecture.md` for the producer/consumer diagram required by
the report.

## Repo layout

```
Lab-2-Yelp/
├── backend/                    # shared Python codebase
│   ├── app/
│   │   ├── main.py             # picks routers by SERVICE_NAME env var
│   │   ├── config.py           # Pydantic settings (MONGO_URI, KAFKA_*, SECRET_KEY)
│   │   ├── database.py         # Motor client + index bootstrap
│   │   ├── dependencies.py     # JWT + session validation
│   │   ├── kafka_utils/        # producer / consumer helpers + topic names
│   │   ├── models/             # doc_out helper (Pydantic schemas live in schemas/)
│   │   ├── routers/            # auth, users, preferences, restaurants, reviews, owner
│   │   ├── schemas/            # request/response models
│   │   ├── services/           # Mongo operations + session store + bcrypt auth
│   │   └── workers/            # review_worker, restaurant_worker, user_worker
│   ├── seed_mongo.py           # one-shot Mongo seed from backend/yelp/
│   └── requirements.txt
├── services/                   # per-API-service Dockerfiles
│   ├── user-api/Dockerfile
│   ├── owner-api/Dockerfile
│   ├── restaurant-api/Dockerfile
│   └── review-api/Dockerfile
├── workers/                    # per-worker Dockerfiles
│   ├── review-worker/Dockerfile
│   ├── restaurant-worker/Dockerfile
│   └── user-worker/Dockerfile
├── frontend/                   # React + Vite + Redux Toolkit
│   ├── src/store/              # store + 4 slices
│   ├── Dockerfile              # Vite build → nginx
│   └── nginx.conf              # routes traffic to the 4 API services
├── k8s/                        # manifests (ns, configmap/secret, mongo, kafka, apis, workers, frontend)
├── jmeter/                     # yelp-load-test.jmx + README
├── docs/architecture.md        # producer/consumer diagram
└── docker-compose.yml
```

## Running locally (Docker Compose)

Docker Desktop is the only prerequisite.

```bash
# 1. Build and start the stack
docker compose up --build -d

# 2. Seed Mongo with restaurants bundled in backend/yelp/yelp_businesses.json
docker compose exec restaurant-api python seed_mongo.py

# 3. Open the frontend
open http://localhost:8080
```

Services:
- Frontend: http://localhost:8080
- user-api, owner-api, restaurant-api, review-api: reachable through the
  frontend's nginx (`/api/v1/...`)
- MongoDB: `mongodb://localhost:27017` (volume `mongo_data`)
- Kafka bootstrap (host): `localhost:29092`; inside the compose network:
  `kafka:9092`

Tear down:

```bash
docker compose down          # keep data
docker compose down -v       # wipe Mongo volume + logs
```

## Running on Kubernetes (Docker Desktop)

1. Enable Kubernetes in Docker Desktop settings.
2. Build images into the local Docker daemon (Docker Desktop's k8s uses
   the same daemon):

   ```bash
   ./k8s/build-images.sh
   ```

3. Apply manifests:

   ```bash
   kubectl apply -f k8s/
   kubectl -n yelp get pods -w
   ```

4. Port-forward the frontend (or use its NodePort 30080):

   ```bash
   kubectl -n yelp port-forward svc/frontend 8080:80
   ```

5. Seed Mongo inside the cluster:

   ```bash
   kubectl -n yelp exec deploy/restaurant-api -- python seed_mongo.py
   ```

## Frontend dev (Vite hot reload)

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8080/api/v1 npm run dev
```

Open http://localhost:5173. The Vite dev server won't proxy through the
nginx container, so the env var points axios at the compose-deployed
gateway.

## Redux DevTools

Redux Toolkit wires the DevTools extension automatically. Install the
browser extension and open the *Redux* tab to inspect state changes
(required screenshots in the Lab 2 report).

## JMeter

See `jmeter/README.md` for the exact CLI invocations at 100/200/300/400/500
users.

## Notes for the Lab 2 report

- Screenshots of services running on AWS / Docker Desktop k8s come from
  `kubectl -n yelp get pods` after `k8s/build-images.sh && kubectl apply -f k8s/`.
- Kafka message flow can be observed with:

  ```bash
  kubectl -n yelp exec -it deploy/kafka -- \
    kafka-console-consumer --bootstrap-server kafka:9092 \
                           --topic review.created --from-beginning
  ```

- MongoDB collections are created on first write. Inspect with:

  ```bash
  kubectl -n yelp exec -it statefulset/mongo -- mongosh yelp_db
  ```
