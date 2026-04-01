import React, { useState, useEffect } from 'react';
import { ordersAPI } from '../services/api';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface MicroserviceFlowProps {
  status: number;
  orderId: string;
}

interface ServiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  logs: string;
}

const ServiceModal: React.FC<ServiceModalProps> = ({ isOpen, onClose, title, logs }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" onClick={onClose}>
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 transition-opacity bg-gray-900 bg-opacity-75" />

        <span className="hidden sm:inline-block sm:align-middle sm:h-screen">&#8203;</span>

        <div
          className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">{title}</h3>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-500 focus:outline-none"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
            <div
              className="bg-gray-50 p-4 rounded-lg font-mono text-xs overflow-y-auto"
              style={{ maxHeight: '60vh' }}
              dangerouslySetInnerHTML={{ __html: logs || 'No logs available' }}
            />
          </div>
          <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              onClick={onClose}
              className="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:w-auto sm:text-sm"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const MicroserviceFlow: React.FC<MicroserviceFlowProps> = ({ status, orderId }) => {
  const [modalOpen, setModalOpen] = useState<string | null>(null);
  const [logs, setLogs] = useState<any>({});

  useEffect(() => {
    loadLogs();
    const interval = setInterval(loadLogs, 2000);
    return () => clearInterval(interval);
  }, [orderId]);

  const loadLogs = async () => {
    try {
      const response = await ordersAPI.getLogs(orderId);
      if (response.data) {
        setLogs(response.data);
      }
    } catch (error) {
      console.error('Failed to load logs:', error);
    }
  };

  const getBorderColor = (serviceName: string) => {
    const grey = '#dee2e6';
    const green = '#198754';
    const red = '#dc3545';
    const blue = '#0d6efd';

    if (serviceName === 'webapp') {
      return status === 0 ? green : grey;
    } else if (serviceName === 'assembly') {
      return status === 100 ? green : grey;
    } else if (serviceName === 'bake') {
      return status === 200 ? green : grey;
    } else if (serviceName === 'delivery') {
      return status === 300 ? green : grey;
    } else if (serviceName === 'status') {
      if ([50, 150, 410, 430, 499].includes(status)) {
        return red;
      } else if (status === 999) {
        return blue;
      }
      return grey;
    }
    return grey;
  };

  const openModal = (service: string) => {
    setModalOpen(service);
  };

  const ServiceCard: React.FC<{
    name: string;
    image: string;
    label: string;
    id: string;
    clickable?: boolean;
  }> = ({ name, image, label, id, clickable = false }) => (
    <div
      id={id}
      className={`border-2 transition-all duration-300 bg-white h-full ${
        clickable ? 'cursor-pointer hover:scale-105 hover:shadow-xl' : ''
      }`}
      style={{ borderColor: getBorderColor(name) }}
      onClick={clickable ? () => openModal(name) : undefined}
    >
      <div className="flex flex-col items-center justify-center p-4 h-full">
        <img
          src={`/static/images/${image}`}
          alt={label}
          className="w-20 h-20 mb-2"
        />
        <div className="text-center font-semibold text-sm">{label}</div>
      </div>
    </div>
  );

  return (
    <>
      <div className="overflow-x-auto">
        <table className="border-collapse mx-auto" style={{ borderSpacing: 0 }}>
          <tbody>
            {/* Top arrow path - Web App → Delivery */}
            <tr style={{ height: '40px' }}>
              <td style={{ width: '140px' }}></td>
              <td style={{ width: '50px' }}></td>
              {/* Up from Web App and turn right */}
              <td style={{ width: '140px', position: 'relative', padding: 0 }}>
                <svg width="100%" height="40" style={{ display: 'block' }} preserveAspectRatio="none" viewBox="0 0 140 40">
                  <line x1="70" y1="40" x2="70" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                  <line x1="70" y1="10" x2="140" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                </svg>
              </td>
              {/* Horizontal line across services */}
              <td style={{ width: '50px', position: 'relative', padding: 0 }}>
                <svg width="100%" height="40" style={{ display: 'block' }} preserveAspectRatio="none" viewBox="0 0 50 40">
                  <line x1="0" y1="10" x2="50" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                </svg>
              </td>
              <td style={{ width: '140px', position: 'relative', padding: 0 }}>
                <svg width="100%" height="40" style={{ display: 'block' }} preserveAspectRatio="none" viewBox="0 0 140 40">
                  <line x1="0" y1="10" x2="140" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                </svg>
              </td>
              <td style={{ width: '50px', position: 'relative', padding: 0 }}>
                <svg width="100%" height="40" style={{ display: 'block' }} preserveAspectRatio="none" viewBox="0 0 50 40">
                  <line x1="0" y1="10" x2="50" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                </svg>
              </td>
              <td style={{ width: '140px', position: 'relative', padding: 0 }}>
                <svg width="100%" height="40" style={{ display: 'block' }} preserveAspectRatio="none" viewBox="0 0 140 40">
                  <line x1="0" y1="10" x2="140" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                </svg>
              </td>
              <td style={{ width: '50px', position: 'relative', padding: 0 }}>
                <svg width="100%" height="40" style={{ display: 'block' }} preserveAspectRatio="none" viewBox="0 0 50 40">
                  <line x1="0" y1="10" x2="50" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                </svg>
              </td>
              {/* Down to Delivery with arrowhead */}
              <td style={{ width: '140px', position: 'relative', padding: 0 }}>
                <svg width="100%" height="40" style={{ display: 'block' }} preserveAspectRatio="none" viewBox="0 0 140 40">
                  <line x1="0" y1="10" x2="70" y2="10" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                  <line x1="70" y1="10" x2="70" y2="40" stroke="#666" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                  <polygon points="70,40 65,32 75,32" fill="#666"/>
                </svg>
              </td>
            </tr>

            {/* Main services row */}
            <tr style={{ height: '150px' }}>
              <td rowSpan={3} style={{ width: '140px', height: '330px' }}>
                <div className="h-full">
                  <ServiceCard name="cache" image="cache.png" label="Local Cache" id="cache-cell" />
                </div>
              </td>
              <td className="text-center" style={{ verticalAlign: 'middle' }}>
                <img src="/static/images/arrow-bi.png" alt="" className="w-12" />
              </td>
              <td style={{ width: '140px' }}>
                <ServiceCard
                  name="webapp"
                  image="store.png"
                  label="Web App"
                  id="webapp-cell"
                  clickable={true}
                />
              </td>
              <td className="text-center" style={{ verticalAlign: 'middle' }}>
                <img src="/static/images/arrow-right.png" alt="" className="w-12" />
              </td>
              <td style={{ width: '140px' }}>
                <ServiceCard
                  name="assembly"
                  image="assemble.png"
                  label="Assemble"
                  id="assembly-cell"
                  clickable={true}
                />
              </td>
              <td className="text-center" style={{ verticalAlign: 'middle' }}>
                <img src="/static/images/arrow-right.png" alt="" className="w-12" />
              </td>
              <td style={{ width: '140px' }}>
                <ServiceCard
                  name="bake"
                  image="oven.png"
                  label="Bake"
                  id="bake-cell"
                  clickable={true}
                />
              </td>
              <td className="text-center" style={{ verticalAlign: 'middle' }}>
                <img src="/static/images/arrow-right.png" alt="" className="w-12" />
              </td>
              <td style={{ width: '140px' }}>
                <ServiceCard
                  name="delivery"
                  image="delivery.png"
                  label="Delivery"
                  id="delivery-cell"
                  clickable={true}
                />
              </td>
            </tr>

            {/* Middle arrow row */}
            <tr style={{ height: '30px' }}>
              <td></td>
              <td></td>
              <td className="text-center">
                <img src="/static/images/arrow-down-right.png" alt="" className="w-12" />
              </td>
              <td className="text-center">
                <img src="/static/images/arrow-down.png" alt="" className="w-12" />
              </td>
              <td></td>
              <td className="text-center">
                <img src="/static/images/arrow-down.png" alt="" className="w-12" />
              </td>
              <td></td>
              <td className="text-center">
                <img src="/static/images/arrow-down.png" alt="" className="w-12" />
              </td>
            </tr>

            {/* Bottom row - Status and Stream Processor same height */}
            <tr style={{ height: '150px' }}>
              <td className="text-center" style={{ verticalAlign: 'middle' }}>
                <img src="/static/images/arrow-bi.png" alt="" className="w-12" />
              </td>
              <td style={{ width: '140px', height: '150px' }}>
                <div className="h-full">
                  <ServiceCard
                    name="status"
                    image="status.png"
                    label="Status"
                    id="status-cell"
                    clickable={true}
                  />
                </div>
              </td>
              <td className="text-center" style={{ verticalAlign: 'middle' }}>
                <img src="/static/images/arrow-left.png" alt="" className="w-12" />
              </td>
              <td colSpan={5} style={{ width: '700px', height: '150px' }}>
                <div className="border-2 border-gray-300 bg-white h-full flex items-center justify-center px-6">
                  <img src="/static/images/flink.png" alt="Stream Processor" className="w-16 h-16 mr-4" />
                  <div className="font-bold text-lg">Stream Processor</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Modals for each service */}
      <ServiceModal
        isOpen={modalOpen === 'webapp'}
        onClose={() => setModalOpen(null)}
        title="Web Application"
        logs={logs.webapp || ''}
      />
      <ServiceModal
        isOpen={modalOpen === 'assembly'}
        onClose={() => setModalOpen(null)}
        title="Microservice Assemble"
        logs={logs.msvc_assemble || ''}
      />
      <ServiceModal
        isOpen={modalOpen === 'bake'}
        onClose={() => setModalOpen(null)}
        title="Microservice Bake"
        logs={logs.msvc_bake || ''}
      />
      <ServiceModal
        isOpen={modalOpen === 'delivery'}
        onClose={() => setModalOpen(null)}
        title="Microservice Delivery"
        logs={logs.msvc_delivery || ''}
      />
      <ServiceModal
        isOpen={modalOpen === 'status'}
        onClose={() => setModalOpen(null)}
        title="Microservice Status"
        logs={logs.msvc_status || ''}
      />
    </>
  );
};

export default MicroserviceFlow;
