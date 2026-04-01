import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ordersAPI, OrderDetail as OrderDetailType } from '../services/api';
import { ClockIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import MicroserviceFlow from '../components/MicroserviceFlow';

const OrderDetail: React.FC = () => {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const [orderDetail, setOrderDetail] = useState<OrderDetailType | null>(null);
  const [logs, setLogs] = useState<string>('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading, setLoading] = useState(true);
  const logsRef = useRef<HTMLDivElement>(null);
  const lastStatus = useRef<number>(-1);
  const isDelivered = useRef(false);

  useEffect(() => {
    if (orderId) {
      loadOrderDetail();
      updateLogs(); // Load logs immediately
      const statusInterval = setInterval(updateOrderStatus, 500);
      const logsInterval = setInterval(updateLogs, 1000);

      return () => {
        clearInterval(statusInterval);
        clearInterval(logsInterval);
      };
    }
  }, [orderId]);

  useEffect(() => {
    if (autoScroll && logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const loadOrderDetail = async () => {
    if (!orderId) return;

    try {
      const response = await ordersAPI.getOrder(orderId);
      setOrderDetail(response.data);
      lastStatus.current = response.data.status;
      isDelivered.current = response.data.status === response.data.status_delivered;
      setLoading(false);
    } catch (err: any) {
      // If order not found (404), redirect to NotFound page
      if (err.response?.status === 404) {
        navigate('/404', { replace: true });
      } else {
        setLoading(false);
      }
    }
  };

  const updateOrderStatus = async () => {
    if (!orderId || isDelivered.current) return;

    try {
      const response = await ordersAPI.getOrderStatus(orderId);
      if (response.data) {
        setOrderDetail((prev) => {
          if (prev) {
            return { ...prev, status: response.data.status, status_str: response.data.str };
          }
          return prev;
        });

        if (orderDetail && response.data.status === orderDetail.status_delivered) {
          isDelivered.current = true;
        }

        lastStatus.current = response.data.status;
      }
    } catch (err) {
      console.error('Failed to update order status:', err);
    }
  };

  const updateLogs = async () => {
    if (!orderId) return;

    try {
      const response = await ordersAPI.getLogs(orderId);
      if (response.data) {
        // Extract all_logs from the response
        const allLogs = response.data.all_logs || 'No logs available yet for this order';
        console.log('Logs received:', allLogs); // Debug
        setLogs(allLogs);
      }
    } catch (err) {
      console.error('Failed to update logs:', err);
      setLogs('Error loading logs');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!orderDetail) {
    return null; // Will redirect to 404
  }

  const isOrderDelivered = orderDetail.status === orderDetail.status_delivered;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2 flex items-center">
          <svg
            className="h-10 w-10 mr-3 text-blue-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          Order Status
        </h1>
        <p className="text-gray-600">Track your pizza order in real-time</p>
      </div>

      {/* Order Information Card */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-4">
          <h2 className="text-xl font-semibold flex items-center">
            <svg className="h-6 w-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
            </svg>
            Order Information
          </h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-8 gap-6">
            <div className="flex items-start space-x-3 lg:col-span-1 md:col-span-1">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
              </div>
              <div>
                <p className="text-sm text-gray-500">Order ID</p>
                <p className="font-semibold text-gray-900">{orderDetail.order_id}</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 lg:col-span-2 md:col-span-1">
              <ClockIcon className="h-6 w-6 text-blue-600 flex-shrink-0" />
              <div>
                <p className="text-sm text-gray-500">Order Time</p>
                <p className="font-semibold text-gray-900">{orderDetail.timestamp}</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 lg:col-span-3 md:col-span-1">
              <CheckCircleIcon className="h-6 w-6 text-blue-600 flex-shrink-0" />
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <span
                  className={`inline-block px-4 py-1 rounded-full text-sm font-semibold ${
                    isOrderDelivered
                      ? 'bg-green-100 text-green-800'
                      : 'bg-blue-100 text-blue-800 animate-pulse-slow'
                  }`}
                >
                  {orderDetail.status_str}
                </span>
              </div>
            </div>

            <div className="flex items-start space-x-3 lg:col-span-2 md:col-span-1">
              <svg className="h-6 w-6 text-blue-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div>
                <p className="text-sm text-gray-500">Details</p>
                <div className="text-sm text-gray-900">
                  <p>Sauce: {orderDetail.sauce}</p>
                  <p>Cheese: {orderDetail.cheese}</p>
                  <p>Main: {orderDetail.topping}</p>
                  <p>Extras: {orderDetail.extras}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Microservice Flow */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        <div className="bg-gradient-to-r from-green-600 to-teal-600 text-white px-6 py-4">
          <h2 className="text-xl font-semibold flex items-center">
            <svg className="h-6 w-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Microservice Flow
          </h2>
        </div>
        <div className="p-6">
          <MicroserviceFlow status={orderDetail.status} orderId={orderId!} />
        </div>
      </div>

      {/* Logs */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        <div className="bg-gradient-to-r from-gray-800 to-gray-900 text-white px-6 py-4 flex justify-between items-center">
          <h2 className="text-xl font-semibold flex items-center">
            <svg className="h-6 w-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            Real-time Logs
          </h2>
          <label className="flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="mr-2 h-4 w-4 text-green-600 rounded focus:ring-2 focus:ring-green-500"
            />
            <span className="text-sm">Auto scroll</span>
          </label>
        </div>
        <div
          ref={logsRef}
          className="p-4 bg-gray-50 font-mono text-xs sm:text-sm overflow-y-auto"
          style={{ height: '400px' }}
          dangerouslySetInnerHTML={{ __html: logs || 'Waiting for logs...' }}
        />
      </div>
    </div>
  );
};

export default OrderDetail;
