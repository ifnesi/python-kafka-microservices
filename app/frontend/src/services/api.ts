import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface MenuData {
  sauces: string[];
  cheeses: string[];
  main_toppings: string[];
  extra_toppings: string[];
}

export interface OrderRequest {
  sauce: string;
  cheese: string;
  main_topping: string;
  extra_toppings: string[];
}

export interface OrderResponse {
  success: boolean;
  order_id: string;
}

export interface OrderDetail {
  order_id: string;
  timestamp: string;
  status: number;
  status_str: string;
  status_delivered: number;
  username: string;
  sauce: string;
  cheese: string;
  topping: string;
  extras: string;
}

export interface OrderStatus {
  str: string;
  status: number;
}

export interface OrdersResponse {
  orders: {
    [key: string]: {
      timestamp: string;
      status_str: string;
    };
  };
}

export interface LogsResponse {
  all_logs: string;
  webapp?: string;
  msvc_assemble?: string;
  msvc_bake?: string;
  msvc_delivery?: string;
  msvc_status?: string;
}

export const authAPI = {
  checkAuth: () => api.get('/auth/check'),
  login: (username: string) => api.post('/auth/login', { username }),
  logout: () => api.post('/auth/logout'),
};

export const menuAPI = {
  getMenu: () => api.get<MenuData>('/menu'),
};

export const ordersAPI = {
  createOrder: (order: OrderRequest) => api.post<OrderResponse>('/orders', order),
  getOrders: () => api.get<OrdersResponse>('/orders'),
  getOrder: (orderId: string) => api.get<OrderDetail>(`/orders/${orderId}`),
  getOrderStatus: (orderId: string) => api.get<OrderStatus>(`/orders/${orderId}/status`),
  getLogs: (orderId: string) => api.get<LogsResponse>(`/logs/${orderId}`),
};

export default api;
