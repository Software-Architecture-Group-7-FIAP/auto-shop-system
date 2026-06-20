# LLM Guide: Build a Car-Service–Style Angular Frontend for an Existing FastAPI Backend

This document teaches an LLM how to reproduce the **Car Service frontend** (`car-service/frontend`) for another application whose backend already exists in **Python + FastAPI**. Read the reference codebase alongside this guide.

---

## 1. What You Are Building

A **single-page admin-style CRUD UI** with:

- A **home menu** linking to entity pages
- One **route per entity** (e.g. `/orders`, `/cars`)
- On each entity page: a **two-column master–detail layout**
  - Left: scrollable **list** of records
  - Right: **detail form** (edit) or **create form** (new record)
- **No UI component library** — plain CSS, Google Fonts, Material Symbols icons
- **Template-driven forms** (`FormsModule`, `ngModel`) with HTML5 validation
- **Angular HttpClient** services that call REST endpoints under `/api/*`

The reference app manages 6 entities: Orders, Cars, Owners, Masters, Services, Goods.

---

## 2. Reference Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | Angular 15 (NgModule-based, not standalone) |
| Language | TypeScript ~4.9 |
| HTTP | `@angular/common/http` + RxJS |
| Forms | `@angular/forms` (template-driven) |
| Routing | `@angular/router` |
| Styling | Global CSS in `src/styles.css` + small per-component CSS |
| Dev proxy | `proxy.conf.json` → forwards `/api/*` to backend |
| Tests | Karma + Jasmine (optional; mirror reference if requested) |

**Do not add** Angular Material, Bootstrap, or Tailwind unless explicitly asked. The visual identity comes from shared CSS classes.

---

## 3. Reference Folder Structure

Replicate this layout for each new entity `{entity}` (plural route name, singular model name):

```
frontend/
├── angular.json
├── package.json
├── proxy.conf.json
├── tsconfig.json
└── src/
    ├── index.html
    ├── main.ts
    ├── styles.css                 # global design system
    └── app/
        ├── app.module.ts
        ├── app-routing.module.ts
        ├── app.component.html     # only <router-outlet>
        ├── model/
        │   └── {entity}.ts        # TypeScript interface (+ enums)
        ├── service/
        │   ├── {entity}.service.ts
        │   └── http-error.interceptor.ts
        └── component/
            ├── menu/
            ├── head-navigation/   # shared header: back, title, add
            └── {entities}/
                ├── {entities}.component.ts|html|css
                ├── {entity}-detail/
                └── new-{entity}/
```

Naming convention in the reference:

- Folder: `cars`, component class: `CarsComponent`, selector: `app-cars`
- Detail: `CarDetailComponent`, selector: `app-car-detail`
- Create: `NewCarComponent`, selector: `app-new-car`
- Service: `CarService`, model file: `model/car.ts`

---

## 4. FastAPI Backend: What Must Already Exist (or Be Added)

The reference frontend assumes a REST API with these conventions. Map your FastAPI app to match **or** adjust the Angular service URLs accordingly.

### 4.1 URL prefix

Reference backend serves everything under `/api` (Spring `context-path=/api`). Frontend services call relative paths like `api/cars`.

**FastAPI setup:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Angular dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
# api.include_router(cars_router, prefix="/cars", tags=["cars"])
app.include_router(api)
```

During development, Angular proxy sends `http://localhost:4200/api/...` → `http://localhost:{BACKEND_PORT}/api/...`.

### 4.2 HTTP verbs and update pattern

The reference frontend uses **POST for both create and update** (not PUT/PATCH):

| Operation | Method | Path | Body |
|-----------|--------|------|------|
| List all | `GET` | `/api/{entities}` | — |
| Get one | `GET` | `/api/{entities}/{id}` | — |
| Create | `POST` | `/api/{entities}` | request DTO (no `id`) |
| Update | `POST` | `/api/{entities}/{id}` | request DTO (fields only, no `id` in body) |

If your FastAPI app uses `PUT`/`PATCH`, change the Angular service — do not silently assume POST works.

**FastAPI example (car):**

```python
@router.get("", response_model=list[CarResponse])
def list_cars(): ...

@router.get("/{car_id}", response_model=CarResponse)
def get_car(car_id: int): ...

@router.post("", response_model=CarResponse)
def create_car(body: CarCreate): ...

@router.post("/{car_id}", response_model=CarResponse)
def update_car(car_id: int, body: CarUpdate): ...
```

### 4.3 JSON field naming

Use **camelCase** in JSON to match TypeScript interfaces (`ownerId`, `carIds`, `orderTime`). FastAPI/Pydantic default is snake_case — configure aliases:

```python
from pydantic import BaseModel, ConfigDict

def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

class CarResponse(CamelModel):
    id: int
    brand: str
    model: str
    year: int
    number: str
    owner_id: int  # serializes as ownerId
```

Alternatively, set `response_model_by_alias=True` on routes and use `Field(alias="ownerId")`.

### 4.4 Dates and numbers

- Dates: ISO-8601 strings (`2024-01-15T10:30:00`) — Angular `date` pipe parses them
- Decimals/prices: JSON numbers (`1250.50`), not strings
- IDs: integers in JSON

### 4.5 Sub-resource and action endpoints (reference patterns)

Some entities expose extra routes. Implement matching FastAPI endpoints if the UI needs them:

| Entity | Extra endpoints |
|--------|-----------------|
| Orders | `GET /orders/{id}/price`, `POST /orders/{id}/status` body `{ "name": "<status>" }` |
| Masters | `GET /masters/{id}/salary`, `GET /masters/{id}/orders` |
| Owners | `POST /owners` with **empty body** creates owner, `GET /owners/{id}/orders` |
| Services | `POST /services/{id}/status` body `{ "name": "<status>" }` |

Status update body shape (critical):

```json
{ "name": "Accepted" }
```

Not `{ "status": "..." }` — the reference Angular code sends `name`.

### 4.6 OpenAPI as source of truth

Before generating models/services, read:

- `http://localhost:{PORT}/docs` or `/openapi.json`

Extract: path, method, request schema, response schema, enum values. TypeScript interfaces must mirror response shapes exactly.

---

## 5. Bootstrap the Angular Project

```bash
npm install -g @angular/cli@15
ng new frontend --routing --style=css --skip-git
cd frontend
```

Edit `package.json` start script:

```json
"start": "ng serve --proxy-config proxy.conf.json"
```

Create `proxy.conf.json` (set `target` to your FastAPI port):

```json
{
  "/api/*": {
    "target": "http://localhost:8000",
    "secure": false,
    "logLevel": "debug",
    "changeOrigin": true
  }
}
```

Copy `src/styles.css` from the reference project verbatim — it is the entire design system.

Update `src/index.html`:

- Title for your app
- Material Symbols font link (used by head navigation icons)
- Montserrat is loaded from `styles.css`

---

## 6. App Module Wiring

Register once in `app.module.ts`:

```typescript
imports: [
  BrowserModule,
  FormsModule,
  AppRoutingModule,
  HttpClientModule,
],
providers: [
  {
    provide: HTTP_INTERCEPTORS,
    useClass: HttpErrorInterceptor,
    multi: true,
  },
],
```

Every feature component is declared in `declarations` (reference uses NgModule, not standalone components).

---

## 7. Routing

Pattern from `app-routing.module.ts`:

```typescript
const routes: Routes = [
  { path: '', redirectTo: '/menu', pathMatch: 'full' },
  { path: 'menu', component: MenuComponent },
  { path: 'orders', component: OrdersComponent },
  // one route per entity list page
];
```

- **No child routes** for detail/create — selection is in-component state
- Menu uses `routerLink="/orders"` etc.

---

## 8. Core UI Pattern (Repeat for Every Entity)

### 8.1 List page component (`{entities}.component.ts`)

State:

```typescript
entities: Entity[] = [];
selectedEntityId: number | undefined;
creatingNewEntity: boolean = false;
```

Lifecycle:

1. `ngOnInit` → call service `getAll()`, sort by `id` ascending
2. `selectEntity(id)` → set `selectedEntityId`, clear `creatingNewEntity`
3. `toCreatingMode` → clear selection, set `creatingNewEntity = true` (pass to head navigation)
4. `updateEntityInList(entity)` → find by id in array and replace (keeps list in sync after edit)

Template layout (always the same skeleton):

```html
<div class="wrapper">
  <div class="navigation-block">
    <app-head-navigation [titleText]="'Cars'" [toCreatingMode]="toCreatingMode"></app-head-navigation>
  </div>
  <div class="model-list-block scrollbar">
    <ul class="model-list">
      <li class="list-header">...</li>
      <li *ngFor="let item of entities" class="list-item" (click)="selectEntity(item.id)"
          [class.selected]="item.id == selectedEntityId">
        <!-- columns -->
      </li>
    </ul>
  </div>
  <div class="model-detail-block scrollbar">
    <span *ngIf="!selectedEntityId && !creatingNewEntity" class="model-detail-message">
      You have not selected any ...
    </span>
    <app-entity-detail *ngIf="selectedEntityId" [entityId]="selectedEntityId"></app-entity-detail>
    <app-new-entity *ngIf="creatingNewEntity"></app-new-entity>
  </div>
</div>
```

List column widths: define `.col-1`, `.col-2`, ... in the entity's component CSS with `flex-basis`.

### 8.2 Head navigation (shared)

Inputs:

- `titleText: string` — page title
- `toCreatingMode: () => void` — arrow handler for the `+` icon

Back link: `<a href="/">` (returns to menu at `/` → redirects to `/menu`).

### 8.3 Detail component (`{entity}-detail.component.ts`)

- `@Input() set entityId(value: number)` — reset dirty flag when selection changes
- `implements OnChanges` → fetch entity when id changes
- Inject **parent list component** to call `updateEntityInList` after save
- `isEntityChanged: boolean` — enable Update button only when user edited fields
- Form: `#formRef="ngForm"`, `[(ngModel)]` on fields, `(ngModelChange)="entityChanged()"`
- Update button: `[disabled]="formRef.invalid || !isEntityChanged"`
- Build request **body with only writable fields** (exclude read-only `id`, timestamps, computed fields)

Read-only fields: display with `<label>{{ value }}</label>` or date pipe — do not bind with ngModel.

### 8.4 Create component (`new-{entity}.component.ts`)

- Form with `ngModel` (no two-way on create — use `formRef.value`)
- `saveEntity(data)` → POST via service → `window.location.reload()` on success

The reference reloads the whole page after create to refresh the list. Prefer this for parity; optionally refactor to emit an event to the parent later.

Array fields from comma-separated input (orders goods, owner cars):

```typescript
data.goodsIds = data.goodsIds === ''
  ? [] : [...new Set(data.goodsIds.split(/[, ]+/))];
```

Convert string inputs to numbers in the body object before POST if needed.

### 8.5 Enums in templates

Define TypeScript `enum` matching backend string values exactly:

```typescript
export enum OrderStatus {
  ACCEPTED = "Accepted",
  IN_PROCESS = "In process",
  // ...
}
```

In template:

```html
<option *ngFor="let key of statusKeys; let i = index" [value]="statusKeys[i]">
  {{ statusValues[i] }}
</option>
```

In component: `statusKeys = Object.keys(OrderStatus); statusValues = Object.values(OrderStatus);`

**Important:** ngModel on `<select>` must bind the enum **key** or **value** consistently with what the API expects. Reference order detail sends `status` as the enum key in update body but status-only endpoint sends `{ name: status }` where status is the bound select value — verify against your OpenAPI spec.

---

## 9. HTTP Service Pattern

One `@Injectable({ providedIn: 'root' })` service per entity:

```typescript
@Injectable({ providedIn: 'root' })
export class CarService {
  private carUrl = 'api/cars';
  httpOptions = {
    headers: new HttpHeaders({ 'Content-Type': 'application/json' }),
  };

  constructor(private http: HttpClient) {}

  getCars(): Observable<Car[]> {
    return this.http.get<Car[]>(this.carUrl);
  }

  getCar(id: number): Observable<Car> {
    return this.http.get<Car>(`${this.carUrl}/${id}`);
  }

  saveCar(body: object): Observable<Car> {
    return this.http.post<Car>(this.carUrl, body, this.httpOptions);
  }

  updateCar(id: number, body: object): Observable<Car> {
    return this.http.post<Car>(`${this.carUrl}/${id}`, body, this.httpOptions);
  }
}
```

Rules:

- URLs are **relative** (`api/cars`) so the dev proxy works
- Always send `Content-Type: application/json` on POST
- Return types match response DTO interfaces
- Add methods for sub-resources (`calculatePrice`, `updateStatus`, `getOrders`, etc.) only when the UI uses them

---

## 10. TypeScript Model Pattern

One file per entity in `src/app/model/`:

```typescript
export interface Car {
  id: number;
  brand: string;
  model: string;
  year: number;
  number: string;
  ownerId: number;
}
```

- Use `interface`, not class
- Optional fields only if API omits them sometimes (`completionTime?`)
- Arrays: `number[]`, `string[]`
- Enums in the same file when the API returns fixed string states

Generate interfaces from FastAPI OpenAPI schemas; do not guess field names.

---

## 11. HTTP Error Interceptor

Reference behavior: global `catchError` → `alert(error.message)` → rethrow.

Keep this minimal unless asked for toast/snackbar UI. Register in `app.module.ts` as shown in section 6.

For better UX with FastAPI, optionally parse `error.error.detail` (FastAPI validation errors) before alerting.

---

## 12. Global CSS Classes (Design System)

Use these class names consistently — they are defined in `src/styles.css`:

| Class | Purpose |
|-------|---------|
| `.wrapper` | CSS grid: nav full width, list + detail columns |
| `.navigation-block` | Top bar spanning both columns |
| `.model-list-block`, `.model-detail-block` | Scroll areas |
| `.scrollbar` | Custom scrollbar styling |
| `.model-list`, `.list-header`, `.list-item` | Entity list |
| `.model-detail-message` | Empty state text |
| `.detail-title-text` | Detail panel heading |
| `.field-list`, `.field-name` | Form field rows |
| `.text-input`, `.select-input` | Inputs (underline style) |
| `.small-input`, `.medium-input`, `.big-input` | Widths |
| `.button-list` | Centered action buttons |

Color palette (dark emerald theme — see `frontend/docs/instructions.md`):

| Token | Hex | Use |
|-------|-----|-----|
| `--color-base` | `#091413` | Page canvas |
| `--color-surface` | `#285A48` | Nav bar, cards, list headers |
| `--color-primary` | `#408A71` | Buttons, links, focus |
| `--color-accent` | `#B0E4CC` | Titles, selected rows, readable text |

Selected list row: add `[class.selected]="item.id === selectedEntityId"` on `.list-item`.

Responsive: below 1024px, grid collapses to single column (already in `styles.css`).

---

## 13. Step-by-Step Workflow for a New Application

When the user gives you a FastAPI backend and domain entities, follow this order:

### Phase A — Discovery

1. Fetch `/openapi.json` or read `/docs`
2. List all resources, methods, schemas, enums
3. Confirm API prefix (`/api` or other — update proxy + service URLs)
4. Confirm create/update verb (POST vs PUT)
5. Note camelCase vs snake_case — align Pydantic or TypeScript

### Phase B — Scaffold

1. Create Angular project (section 5)
2. Copy global styles and index.html font links
3. Create `app-routing.module.ts` with menu + one route per resource
4. Create `MenuComponent` with links to all routes
5. Create `HeadNavigationComponent`
6. Register `HttpErrorInterceptor`

### Phase C — Per entity (loop)

For each resource `{entities}`:

1. **`model/{entity}.ts`** — interfaces/enums from OpenAPI
2. **`service/{entity}.service.ts`** — HTTP methods
3. **`component/{entities}/{entities}.component.*`** — list page
4. **`component/{entities}/{entity}-detail/*`** — edit panel
5. **`component/{entities}/new-{entity}/*`** — create panel
6. Declare all components in `app.module.ts`
7. Add menu link

### Phase D — Verify

1. Start FastAPI on configured port
2. `npm start` → `http://localhost:4200`
3. For each entity: list loads, select shows detail, update persists, create reloads list
4. Test sub-resource actions (price, status, salary, nested orders)
5. Fix CORS/proxy/field name mismatches first — most bugs are here

---

## 14. Reference Entity Checklist

Use this when parity with the car-service app is desired:

| Entity | Route | Service URL | Special actions |
|--------|-------|-------------|-----------------|
| Orders | `/orders` | `api/orders` | calculate price, update status, comma-separated goodsIds |
| Cars | `/cars` | `api/cars` | — |
| Owners | `/owners` | `api/owners` | create with empty POST body, get orders, comma-separated carIds |
| Masters | `/masters` | `api/masters` | calculate salary, get orders |
| Services | `/services` | `api/services` | update status |
| Goods | `/goods` | `api/goods` | — |

For a **different** domain, keep the same UI architecture but replace entity names, columns, form fields, and service methods.

---

## 15. Code Templates (Minimal)

### Menu (`menu.component.html`)

```html
<div class="menu">
  <p>menu</p>
  <ul>
    <li><a routerLink="/your-entity">Your Entity</a></li>
  </ul>
</div>
```

### FastAPI CORS + router (minimal)

```python
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/items", tags=["items"])

@router.get("")
def list_items(): ...

app.include_router(router)
```

---

## 16. Common Pitfalls (Read Before Coding)

1. **Proxy vs CORS** — Use proxy in dev (`api/...` paths). Still add CORS on FastAPI for direct testing and production.
2. **POST for update** — FastAPI often uses PUT; align one way or the other.
3. **snake_case JSON** — TypeScript expects camelCase; fix on backend with Pydantic aliases.
4. **Enum mismatch** — Angular enum values must match API strings character-for-character (including spaces: `"In process"`).
5. **Status body `{ name: ... }`** — Do not rename to `status` without updating Angular.
6. **Empty POST for owner create** — `createOwner()` sends `null` body; FastAPI route must accept empty body.
7. **Array fields bound as strings** — Detail forms may show arrays as strings; split/join on save like the reference.
8. **`window.location.reload()` after create** — Crude but intentional in reference; list is not refetched via RxJS.
9. **Parent injection in detail** — Detail components inject the list component directly (tight coupling). Acceptable in this app; do not over-engineer with EventEmitter unless requested.
10. **No authentication** — Reference has no login, guards, or JWT interceptors. Add separately if the new app requires auth.

---

## 17. What “Done” Looks Like

- Menu navigates to every entity route
- Each entity page shows list + detail/create with shared styling matching the reference
- All CRUD operations hit the FastAPI backend successfully through the dev proxy
- Forms validate required fields and numeric patterns before submit
- Update buttons disabled until user changes something
- Selected list row highlighted with `.selected` class (mint accent border)
- Layout responsive on narrow screens

---

## 18. Files to Read First in the Reference Repo

| File | Why |
|------|-----|
| `src/styles.css` | Entire design system |
| `src/app/app-routing.module.ts` | Route map |
| `src/app/app.module.ts` | Module declarations |
| `src/app/component/cars/cars.component.*` | Simplest full entity example |
| `src/app/component/orders/order-detail/*` | Enums, actions, read-only fields |
| `src/app/component/owners/owner-detail/*` | Nested fetch, array parsing |
| `src/app/service/car.service.ts` | HTTP service template |
| `proxy.conf.json` | Dev backend URL |

---

*Generated from analysis of `car-service/frontend`. Backend reference was Spring Boot on port 6868 with context path `/api`; adapt ports and framework details for FastAPI.*
