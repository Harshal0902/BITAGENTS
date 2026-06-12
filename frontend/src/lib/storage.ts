export function getLS<T>(key: string, fallback: T): T {
    if (typeof window === "undefined") return fallback;
    const data = localStorage.getItem(key);
    return data ? JSON.parse(data) : fallback;
}

export function setLS<T>(key: string, value: T) {
    if (typeof window === "undefined") return;
    localStorage.setItem(key, JSON.stringify(value));
}