"use client";

import { FormEvent, useEffect, useState } from "react";

type Category = {
  id: number;
  name: string;
};

type Product = {
  id: number;
  name: string;
  description: string;
  price: number;
  categories: Category[];
};

// Open the website at http://127.0.0.1:3000 so the frontend and the backend are
// the SAME SITE (127.0.0.1). Otherwise the browser would not send SameSite=Lax cookies.
// (We use 127.0.0.1 instead of "localhost" because on a Mac "localhost" may go to
// IPv6 ::1, where uvicorn is not listening.)
const BASE_URL = "http://127.0.0.1:8000";
const API_URL = `${BASE_URL}/products`;
const CATEGORIES_API_URL = `${BASE_URL}/categories`;
const REGISTER_URL = `${BASE_URL}/register`;
const LOGIN_URL = `${BASE_URL}/login`;
const LOGOUT_URL = `${BASE_URL}/logout`;
const ME_URL = `${BASE_URL}/me`;
// COOKIE / CORS demo endpoints
const COOKIES_URL = `${BASE_URL}/cookies`;
const FOO_URL = `${BASE_URL}/foo`;

// Every request to the backend goes through here.
// credentials: "include" = send our cookies (incl. the httponly access_token)
// and accept the Set-Cookie headers the backend returns.
function apiFetch(url: string, init: RequestInit = {}) {
  return fetch(url, { ...init, credentials: "include" });
}

type CookieRow = {
  name: string;
  value: string;
  readableByJs: boolean;
};

// Names of the cookies JavaScript is allowed to see (httponly ones are hidden)
function readJsCookieNames(): Set<string> {
  return new Set(
    document.cookie
      .split(";")
      .map((part) => part.split("=")[0].trim())
      .filter(Boolean)
  );
}
// STREAMING endpoints
const STREAM_EVENTS_URL = `${BASE_URL}/stream/events`;
const STREAM_PRODUCTS_URL = `${BASE_URL}/stream/products`;
const EXPORT_CSV_URL = `${BASE_URL}/stream/products/export.csv`;

type LiveEvent = {
  type: string;
  time: string;
  data: {
    user?: string;
    product?: Product;
    category?: Category;
  };
};

const LIVE_EVENT_TYPES = [
  "product_created",
  "product_updated",
  "product_deleted",
  "category_created",
  "category_updated",
  "category_deleted",
];

export default function Home() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [categoryEditName, setCategoryEditName] = useState("");

  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);

  // AUTH STATE
  const [authUsername, setAuthUsername] = useState<string | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");

  // STREAMING STATE
  const [liveConnected, setLiveConnected] = useState(false);
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([]);
  const [streamedProducts, setStreamedProducts] = useState<Product[]>([]);
  const [streamTotal, setStreamTotal] = useState(0);
  const [isStreaming, setIsStreaming] = useState(false);

  // COOKIE / CORS DEMO STATE
  const [cookieRows, setCookieRows] = useState<CookieRow[]>([]);
  const [corsResult, setCorsResult] = useState("");

  function clearMessages() {
    setSuccessMessage("");
    setErrorMessage("");
  }

  function showError(message: string) {
    setErrorMessage(message);
    setSuccessMessage("");
  }

  function showSuccess(message: string) {
    setSuccessMessage(message);
    setErrorMessage("");
  }

  // Safely parse a JSON response body without throwing on empty/invalid bodies
  async function parseJsonSafe(response: Response) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  // COOKIE PANEL: ask the backend which cookies it received,
  // then check which of them JavaScript can also see in document.cookie
  async function loadCookies() {
    try {
      const response = await apiFetch(COOKIES_URL);
      const result = await parseJsonSafe(response);
      const received: Record<string, string> = result?.cookies ?? {};
      const jsNames = readJsCookieNames();
      setCookieRows(
        Object.entries(received).map(([name, value]) => ({
          name,
          value,
          readableByJs: jsNames.has(name),
        }))
      );
    } catch (error) {
      console.error(error);
    }
  }

  // CORS TEST: the custom header forces the browser to send a preflight
  // (OPTIONS) request first. The backend's CORS allows every method except HEAD.
  async function testCors(method: "GET" | "HEAD") {
    setCorsResult(`Sending ${method} /foo ...`);
    try {
      const response = await apiFetch(FOO_URL, {
        method,
        headers: { "X-Demo": "cors-test" },
      });
      setCorsResult(`✅ ${method} /foo -> ${response.status} OK (allowed by CORS)`);
    } catch {
      setCorsResult(
        `🚫 ${method} /foo was blocked by the browser (CORS does not allow ${method}). Open DevTools → Console to see the error.`
      );
    }
  }

  // RESTORE SESSION FROM THE COOKIE
  // After a refresh the httponly cookie is still in the browser, so /me tells us who we are.
  useEffect(() => {
    async function restoreSession() {
      try {
        const response = await apiFetch(ME_URL);
        if (response.ok) {
          const result = await response.json();
          setAuthUsername(result.username);
        }
      } catch {
        // backend not reachable - stay logged out
      }
      loadCookies();
    }

    restoreSession();
    // Run only once when the page opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // GET PRODUCTS
  useEffect(() => {
    async function getProducts() {
      try {
        const response = await apiFetch(API_URL);
        const result = await parseJsonSafe(response);

        if (!response.ok) {
          throw new Error(
            result?.detail || `Failed to fetch products (status ${response.status})`
          );
        }

        setProducts(result ?? []);
      } catch (error) {
        console.error(error);

        if (error instanceof TypeError) {
          // fetch() throws TypeError when the server cannot be reached at all
          showError(
            `Cannot reach the backend at ${BASE_URL}. Is "uvicorn product_app.main:app --reload" running?`
          );
        } else if (error instanceof Error) {
          showError(error.message);
        } else {
          showError("Failed to fetch products");
        }
      } finally {
        setLoading(false);
      }
    }

    getProducts();
  }, []);

  // GET CATEGORIES
  useEffect(() => {
    async function getCategories() {
      try {
        const response = await apiFetch(CATEGORIES_API_URL);
        const result = await parseJsonSafe(response);

        if (!response.ok) {
          throw new Error(
            result?.detail || `Failed to fetch categories (status ${response.status})`
          );
        }

        setCategories(result ?? []);
      } catch (error) {
        console.error(error);
      }
    }

    getCategories();
  }, []);

  // LIVE FEED (Server-Sent Events)
  // Other users' changes arrive here in real time and update the product list.
  useEffect(() => {
    const source = new EventSource(STREAM_EVENTS_URL);

    source.addEventListener("connected", () => setLiveConnected(true));
    source.onerror = () => setLiveConnected(false);

    function handleLiveEvent(event: MessageEvent) {
      const message: LiveEvent = JSON.parse(event.data);
      setLiveEvents((current) => [message, ...current].slice(0, 20));

      const { product, category } = message.data;

      if (product && message.type === "product_deleted") {
        setProducts((current) => current.filter((item) => item.id !== product.id));
      } else if (product) {
        setProducts((current) =>
          current.some((item) => item.id === product.id)
            ? current.map((item) => (item.id === product.id ? product : item))
            : [...current, product]
        );
      }

      if (category && message.type === "category_deleted") {
        setCategories((current) => current.filter((item) => item.id !== category.id));
        setProducts((current) =>
          current.map((item) => ({
            ...item,
            categories: item.categories.filter((c) => c.id !== category.id),
          }))
        );
      } else if (category) {
        setCategories((current) =>
          current.some((item) => item.id === category.id)
            ? current.map((item) => (item.id === category.id ? category : item))
            : [...current, category]
        );
        setProducts((current) =>
          current.map((item) => ({
            ...item,
            categories: item.categories.map((c) => (c.id === category.id ? category : c)),
          }))
        );
      }
    }

    LIVE_EVENT_TYPES.forEach((type) => source.addEventListener(type, handleLiveEvent));

    return () => source.close();
  }, []);

  // STREAM PRODUCTS ONE BY ONE (NDJSON + fetch ReadableStream)
  async function streamProducts() {
    setIsStreaming(true);
    setStreamedProducts([]);
    setStreamTotal(0);

    try {
      const response = await apiFetch(`${STREAM_PRODUCTS_URL}?delay=0.5`);
      if (!response.ok || !response.body) {
        throw new Error(`Stream failed (status ${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? ""; // keep the incomplete last line

        for (const line of lines) {
          if (!line.trim()) continue;
          const chunk = JSON.parse(line);
          if (chunk.type === "start") setStreamTotal(chunk.total);
          if (chunk.type === "product") {
            setStreamedProducts((current) => [...current, chunk.product]);
          }
        }
      }
    } catch (error) {
      showError(error instanceof Error ? error.message : "Stream failed");
    } finally {
      setIsStreaming(false);
    }
  }

  function describeEvent(event: LiveEvent) {
    const who = event.data.user ?? "someone";
    const target = event.data.product?.name ?? event.data.category?.name ?? "";
    const [kind, action] = event.type.split("_");
    return `${who} ${action} ${kind} "${target}"`;
  }

  // REGISTER
  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();

    try {
      const response = await apiFetch(REGISTER_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: registerUsername.trim(),
          password: registerPassword,
        }),
      });

      const result = await parseJsonSafe(response);

      if (!response.ok) {
        throw new Error(
          result?.detail || `Registration failed (status ${response.status})`
        );
      }

      showSuccess("Account created. You can now log in.");
      setLoginUsername(registerUsername.trim());
      setRegisterUsername("");
      setRegisterPassword("");
      setAuthMode("login");
    } catch (error) {
      showError(error instanceof Error ? error.message : "Registration failed");
    }
  }

  // LOGIN
  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();

    try {
      const body = new URLSearchParams();
      body.set("username", loginUsername.trim());
      body.set("password", loginPassword);

      const response = await apiFetch(LOGIN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      const result = await parseJsonSafe(response);

      if (!response.ok) {
        throw new Error(result?.detail || `Login failed (status ${response.status})`);
      }

      // No token in the response - the backend put it in an httponly cookie
      setAuthUsername(result.username);
      setLoginPassword("");
      showSuccess("Logged in successfully (token saved in an httponly cookie)");
      loadCookies();
    } catch (error) {
      showError(error instanceof Error ? error.message : "Login failed");
    }
  }

  // LOGOUT
  async function handleLogout() {
    clearMessages();

    try {
      await apiFetch(LOGOUT_URL, { method: "POST" });
      showSuccess("Logged out successfully (cookies deleted)");
    } catch (error) {
      console.error(error);
    } finally {
      setAuthUsername(null);
      loadCookies();
    }
  }

  // CLEAR FORM
  function clearForm() {
    setId("");
    setName("");
    setDescription("");
    setPrice("");
    setEditingId(null);
  }

  // SELECT PRODUCT FOR EDITING
  function editProduct(product: Product) {
    clearMessages();

    setEditingId(product.id);
    setId(String(product.id));
    setName(product.name);
    setDescription(product.description);
    setPrice(String(product.price));
  }

  // POST PRODUCT
  async function addProduct() {
    const newProduct = {
      id: Number(id),
      name: name.trim(),
      description: description.trim(),
      price: Number(price),
    };

    const response = await apiFetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(newProduct),
    });

    const result = await parseJsonSafe(response);

    if (!response.ok) {
      throw new Error(
        result?.detail || `Failed to add product (status ${response.status})`
      );
    }

    // The SSE live feed may have added it already, so avoid duplicates
    setProducts((currentProducts) => [
      ...currentProducts.filter((product) => product.id !== result.id),
      result,
    ]);

    clearForm();
    showSuccess("Product added successfully");
  }

  // PUT PRODUCT
  async function updateProduct() {
    if (editingId === null) {
      throw new Error("No product selected for editing");
    }

    const updatedProduct = {
      id: editingId,
      name: name.trim(),
      description: description.trim(),
      price: Number(price),
    };

    const response = await apiFetch(`${API_URL}/${editingId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(updatedProduct),
    });

    const result = await parseJsonSafe(response);

    if (!response.ok) {
      throw new Error(
        result?.detail || `Failed to update product (status ${response.status})`
      );
    }

    setProducts((currentProducts) =>
      currentProducts.map((product) =>
        product.id === editingId ? result : product
      )
    );

    clearForm();
    showSuccess("Product updated successfully");
  }

// SUBMIT FORM
  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();

    try {
      if (editingId === null) {
        await addProduct();
      } else {
        await updateProduct();
      }
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      } else {
        showError("Failed to save product");
      }
    }
  }

  // DELETE PRODUCT
  async function deleteProduct(productId: number) {
    clearMessages();

    try {
      const response = await apiFetch(`${API_URL}/${productId}`, {
        method: "DELETE",
      });

      const result = await parseJsonSafe(response);

      if (!response.ok) {
        throw new Error(
          result?.detail || `Failed to delete product (status ${response.status})`
        );
      }

      setProducts((currentProducts) =>
        currentProducts.filter((product) => product.id !== productId)
      );

      if (editingId === productId) {
        clearForm();
      }

      showSuccess(`Product with id ${productId} deleted successfully`);
    } catch (error) {
      console.error(error);

      if (error instanceof Error) {
        showError(error.message);
      } else {
        showError("Failed to delete product");
      }
    }
  }

  // SELECT CATEGORY FOR EDITING
  function editCategory(category: Category) {
    clearMessages();
    setEditingCategoryId(category.id);
    setCategoryEditName(category.name);
  }

  // CANCEL CATEGORY EDIT
  function cancelCategoryEdit() {
    setEditingCategoryId(null);
    setCategoryEditName("");
  }

  // ADD OR UPDATE CATEGORY
  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();

    const isEditing = editingCategoryId !== null;
    const name = (isEditing ? categoryEditName : categoryName).trim();

    try {
      const response = await apiFetch(
        isEditing ? `${CATEGORIES_API_URL}/${editingCategoryId}` : CATEGORIES_API_URL,
        {
          method: isEditing ? "PUT" : "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name }),
        }
      );

      const result = await parseJsonSafe(response);

      if (!response.ok) {
        throw new Error(
          result?.detail ||
            `Failed to ${isEditing ? "update" : "add"} category (status ${response.status})`
        );
      }

      if (isEditing) {
        setCategories((currentCategories) =>
          currentCategories.map((category) =>
            category.id === editingCategoryId ? result : category
          )
        );
        setProducts((currentProducts) =>
          currentProducts.map((product) => ({
            ...product,
            categories: product.categories.map((category) =>
              category.id === editingCategoryId ? result : category
            ),
          }))
        );
        cancelCategoryEdit();
        showSuccess("Category updated successfully");
      } else {
        setCategories((currentCategories) => [
          ...currentCategories.filter((category) => category.id !== result.id),
          result,
        ]);
        setCategoryName("");
        showSuccess("Category added successfully");
      }
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      } else {
        showError(`Failed to ${isEditing ? "update" : "add"} category`);
      }
    }
  }

  // DELETE CATEGORY
  async function deleteCategory(categoryId: number) {
    clearMessages();

    try {
      const response = await apiFetch(`${CATEGORIES_API_URL}/${categoryId}`, {
        method: "DELETE",
      });

      const result = await parseJsonSafe(response);

      if (!response.ok) {
        throw new Error(
          result?.detail || `Failed to delete category (status ${response.status})`
        );
      }

      setCategories((currentCategories) =>
        currentCategories.filter((category) => category.id !== categoryId)
      );
      setProducts((currentProducts) =>
        currentProducts.map((product) => ({
          ...product,
          categories: product.categories.filter(
            (category) => category.id !== categoryId
          ),
        }))
      );

      if (editingCategoryId === categoryId) {
        cancelCategoryEdit();
      }

      showSuccess("Category deleted successfully");
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      } else {
        showError("Failed to delete category");
      }
    }
  }

  // LINK CATEGORY TO PRODUCT
  async function linkCategory(productId: number, category: Category) {
    clearMessages();

    try {
      const response = await apiFetch(
        `${API_URL}/${productId}/categories/${category.id}`,
        { method: "POST" }
      );

      const result = await parseJsonSafe(response);

      if (!response.ok) {
        throw new Error(
          result?.detail || `Failed to add category (status ${response.status})`
        );
      }

      setProducts((currentProducts) =>
        currentProducts.map((product) =>
          product.id === productId
            ? { ...product, categories: [...product.categories, category] }
            : product
        )
      );

      showSuccess("Category added to product");
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      } else {
        showError("Failed to add category to product");
      }
    }
  }

  // UNLINK CATEGORY FROM PRODUCT
  async function unlinkCategory(productId: number, categoryId: number) {
    clearMessages();

    try {
      const response = await apiFetch(
        `${API_URL}/${productId}/categories/${categoryId}`,
        { method: "DELETE" }
      );

      const result = await parseJsonSafe(response);

      if (!response.ok) {
        throw new Error(
          result?.detail || `Failed to remove category (status ${response.status})`
        );
      }

      setProducts((currentProducts) =>
        currentProducts.map((product) =>
          product.id === productId
            ? {
                ...product,
                categories: product.categories.filter(
                  (category) => category.id !== categoryId
                ),
              }
            : product
        )
      );

      showSuccess("Category removed from product");
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      } else {
        showError("Failed to remove category from product");
      }
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-3xl font-bold">
        Product Management
      </h1>

      <section className="mb-8 rounded border p-4">
        {authUsername ? (
          <div className="flex items-center justify-between">
            <p>
              Signed in as <span className="font-semibold">{authUsername}</span>
            </p>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded bg-gray-600 px-3 py-1 text-white hover:bg-gray-700"
            >
              Logout
            </button>
          </div>
        ) : (
          <div>
            <div className="mb-3 flex gap-2">
              <button
                type="button"
                onClick={() => setAuthMode("login")}
                className={`rounded px-3 py-1 ${
                  authMode === "login"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-900"
                }`}
              >
                Login
              </button>
              <button
                type="button"
                onClick={() => setAuthMode("register")}
                className={`rounded px-3 py-1 ${
                  authMode === "register"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-900"
                }`}
              >
                Register
              </button>
            </div>

            {authMode === "login" ? (
              <form onSubmit={handleLogin} className="space-y-2">
                <input
                  type="text"
                  placeholder="Username"
                  value={loginUsername}
                  onChange={(event) => setLoginUsername(event.target.value)}
                  required
                  className="block w-full rounded border p-2"
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={loginPassword}
                  onChange={(event) => setLoginPassword(event.target.value)}
                  required
                  className="block w-full rounded border p-2"
                />
                <button
                  type="submit"
                  className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
                >
                  Login
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-2">
                <input
                  type="text"
                  placeholder="Choose a username"
                  value={registerUsername}
                  onChange={(event) => setRegisterUsername(event.target.value)}
                  required
                  className="block w-full rounded border p-2"
                />
                <input
                  type="password"
                  placeholder="Choose a password"
                  value={registerPassword}
                  onChange={(event) => setRegisterPassword(event.target.value)}
                  required
                  minLength={4}
                  className="block w-full rounded border p-2"
                />
                <button
                  type="submit"
                  className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
                >
                  Create account
                </button>
              </form>
            )}
          </div>
        )}
      </section>

      {authUsername ? (
        <form onSubmit={saveProduct} className="mb-8 space-y-4">
          <h2 className="text-xl font-semibold">
            {editingId === null ? "Add Product" : "Edit Product"}
          </h2>

          <input
            type="number"
            placeholder="Product ID"
            value={id}
            onChange={(event) => setId(event.target.value)}
            required
            readOnly={editingId !== null}
            className="block w-full rounded border p-2 disabled:bg-gray-200"
          />

          <input
            type="text"
            placeholder="Product name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            className="block w-full rounded border p-2"
          />

          <textarea
            placeholder="Product description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            required
            className="block w-full rounded border p-2"
          />

          <input
            type="number"
            step="0.01"
            placeholder="Product price"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            required
            className="block w-full rounded border p-2"
          />

          <button
            type="submit"
            className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          >
            {editingId === null ? "Add Product" : "Update Product"}
          </button>

          {editingId !== null && (
            <button
              type="button"
              onClick={clearForm}
              className="ml-2 rounded bg-gray-500 px-4 py-2 text-white hover:bg-gray-600"
            >
              Cancel
            </button>
          )}
        </form>
      ) : (
        <p className="mb-8 text-gray-500">Log in to add or edit products.</p>
      )}

      {authUsername && (
        <form onSubmit={saveCategory} className="mb-4 flex gap-2">
          <input
            type="text"
            placeholder={editingCategoryId === null ? "New category name" : "Category name"}
            value={editingCategoryId === null ? categoryName : categoryEditName}
            onChange={(event) =>
              editingCategoryId === null
                ? setCategoryName(event.target.value)
                : setCategoryEditName(event.target.value)
            }
            required
            className="flex-1 rounded border p-2"
          />

          <button
            type="submit"
            className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          >
            {editingCategoryId === null ? "Add Category" : "Save Category"}
          </button>

          {editingCategoryId !== null && (
            <button
              type="button"
              onClick={cancelCategoryEdit}
              className="rounded bg-gray-500 px-4 py-2 text-white hover:bg-gray-600"
            >
              Cancel
            </button>
          )}
        </form>
      )}

      {categories.length > 0 && (
        <ul className="mb-8 space-y-1">
          {categories.map((category) => (
            <li
              key={category.id}
              className="flex items-center justify-between rounded border px-3 py-1 text-sm"
            >
              <span>{category.name}</span>
              {authUsername && (
                <span className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => editCategory(category)}
                    className="rounded bg-yellow-500 px-2 py-0.5 text-white hover:bg-yellow-600"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteCategory(category.id)}
                    className="rounded bg-red-600 px-2 py-0.5 text-white hover:bg-red-700"
                  >
                    Delete
                  </button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {successMessage && (
        <p className="mb-4 text-green-600">
          {successMessage}
        </p>
      )}

      {errorMessage && (
        <p className="mb-4 text-red-600">
          {errorMessage}
        </p>
      )}

      <section className="mb-8 rounded border border-dashed border-orange-400 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold">🍪 Cookies the browser is storing</h2>
          <button
            type="button"
            onClick={loadCookies}
            className="rounded bg-gray-200 px-3 py-1 text-gray-900 hover:bg-gray-300"
          >
            Refresh
          </button>
        </div>
        {cookieRows.length === 0 ? (
          <p className="text-sm text-gray-500">No cookies yet. Log in to get some.</p>
        ) : (
          <table className="w-full table-fixed border-collapse text-sm">
            <thead>
              <tr className="bg-gray-100">
                <th className="w-1/4 border p-2 text-left">Cookie name</th>
                <th className="border p-2 text-left">Value (as received by backend)</th>
                <th className="w-1/4 border p-2 text-left">Can JavaScript read it?</th>
              </tr>
            </thead>
            <tbody>
              {cookieRows.map((cookie) => (
                <tr key={cookie.name}>
                  <td className="border p-2 font-mono">{cookie.name}</td>
                  <td className="truncate border p-2 font-mono" title={cookie.value}>
                    {cookie.value}
                  </td>
                  <td className="border p-2">
                    {cookie.readableByJs ? "✅ Yes" : "❌ No (httponly)"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mb-8 rounded border border-dashed p-4">
        <h2 className="mb-3 text-xl font-semibold">
          🚫 CORS test: server allows every method except HEAD
        </h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => testCors("GET")}
            className="rounded bg-gray-200 px-3 py-1 text-gray-900 hover:bg-gray-300"
          >
            Call GET /foo
          </button>
          <button
            type="button"
            onClick={() => testCors("HEAD")}
            className="rounded bg-gray-200 px-3 py-1 text-gray-900 hover:bg-gray-300"
          >
            Call HEAD /foo
          </button>
        </div>
        {corsResult && <p className="mt-2 text-sm">{corsResult}</p>}
      </section>

      <section className="mb-8 rounded border p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Live Activity</h2>
          <span className={liveConnected ? "text-green-500" : "text-red-500"}>
            ● {liveConnected ? "Connected (SSE)" : "Disconnected"}
          </span>
        </div>
        {liveEvents.length === 0 ? (
          <p className="text-sm text-gray-500">
            Waiting for changes... (open this page in two tabs and edit a product)
          </p>
        ) : (
          <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
            {liveEvents.map((event, index) => (
              <li key={`${event.time}-${index}`} className="text-gray-700">
                <span className="text-gray-400">
                  [{new Date(event.time).toLocaleTimeString()}]
                </span>{" "}
                {describeEvent(event)}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-8 rounded border p-4">
        <h2 className="mb-3 text-xl font-semibold">Streaming Tools</h2>
        <div className="mb-3 flex gap-2">
          <button
            type="button"
            onClick={streamProducts}
            disabled={isStreaming}
            className="rounded bg-purple-600 px-4 py-2 text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {isStreaming ? "Streaming..." : "Stream products one by one"}
          </button>
          <a
            href={EXPORT_CSV_URL}
            className="rounded bg-green-600 px-4 py-2 text-white hover:bg-green-700"
          >
            Download CSV (streamed)
          </a>
        </div>
        {(isStreaming || streamedProducts.length > 0) && (
          <div>
            <p className="mb-1 text-sm text-gray-500">
              Received {streamedProducts.length} / {streamTotal}
            </p>
            <div className="mb-2 h-2 w-full rounded bg-gray-200">
              <div
                className="h-2 rounded bg-purple-500 transition-all"
                style={{
                  width: `${streamTotal ? (streamedProducts.length / streamTotal) * 100 : 0}%`,
                }}
              />
            </div>
            <ul className="space-y-1 text-sm">
              {streamedProducts.map((product) => (
                <li key={product.id}>
                  #{product.id} {product.name} - ${product.price}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <h2 className="mb-3 text-xl font-semibold">
        Products
      </h2>

      {loading ? (
        <p>Loading products...</p>
      ) : products.length === 0 ? (
        <p>No products found.</p>
      ) : (
        <ul className="space-y-4">
          {products.map((product) => (
            <li key={product.id} className="rounded border p-4">
              <div className="mb-3">
                <h3 className="text-lg font-semibold">
                  {product.name}
                </h3>

                <p className="text-gray-500">
                  ID: {product.id}
                </p>

                <p className="text-gray-700">
                  {product.description}
                </p>

                <p className="font-semibold text-gray-900">
                  Price: $
                  {product.price.toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </p>

                <div className="text-gray-600">
                  Categories:{" "}
                  {(product.categories ?? []).length === 0 ? (
                    "None"
                  ) : (
                    <span className="inline-flex flex-wrap gap-1 align-middle">
                      {(product.categories ?? []).map((category) => (
                        <span
                          key={category.id}
                          className="inline-flex items-center gap-1 rounded bg-gray-200 px-2 py-0.5 text-gray-800"
                        >
                          {category.name}
                          {authUsername && (
                            <button
                              type="button"
                              onClick={() => unlinkCategory(product.id, category.id)}
                              className="text-red-500 hover:text-red-700"
                              aria-label={`Remove ${category.name} from ${product.name}`}
                            >
                              ×
                            </button>
                          )}
                        </span>
                      ))}
                    </span>
                  )}
                </div>

                {authUsername && (
                  <select
                    key={(product.categories ?? []).length}
                    defaultValue=""
                    onChange={(event) => {
                      const category = categories.find(
                        (item) => String(item.id) === event.target.value
                      );
                      if (category) linkCategory(product.id, category);
                    }}
                    className="mt-2 rounded border bg-white p-1 text-sm text-gray-900"
                  >
                    <option value="" disabled>
                      Add category...
                    </option>
                    {categories
                      .filter(
                        (category) =>
                          !(product.categories ?? []).some((item) => item.id === category.id)
                      )
                      .map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                  </select>
                )}
              </div>

              {authUsername && (
                <>
                  <button
                    type="button"
                    onClick={() => editProduct(product)}
                    className="mr-2 rounded bg-yellow-500 px-3 py-1 text-white hover:bg-yellow-600"
                  >
                    Edit
                  </button>

                  <button
                    type="button"
                    onClick={() => deleteProduct(product.id)}
                    className="rounded bg-red-600 px-3 py-1 text-white hover:bg-red-700"
                  >
                    Delete
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
