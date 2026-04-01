import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { menuAPI, ordersAPI, MenuData } from '../services/api';

const Menu: React.FC = () => {
  const [menuData, setMenuData] = useState<MenuData | null>(null);
  const [selectedSauce, setSelectedSauce] = useState('');
  const [selectedCheese, setSelectedCheese] = useState('');
  const [selectedMainTopping, setSelectedMainTopping] = useState('');
  const [selectedExtraToppings, setSelectedExtraToppings] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadMenu();
  }, []);

  const loadMenu = async () => {
    try {
      const response = await menuAPI.getMenu();
      setMenuData(response.data);
    } catch (error) {
      console.error('Failed to load menu:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExtraToppingToggle = (topping: string) => {
    setSelectedExtraToppings((prev) =>
      prev.includes(topping)
        ? prev.filter((t) => t !== topping)
        : [...prev, topping]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedSauce || !selectedCheese || !selectedMainTopping) {
      alert('Please select sauce, cheese, and main topping');
      return;
    }

    setSubmitting(true);
    try {
      const response = await ordersAPI.createOrder({
        sauce: selectedSauce,
        cheese: selectedCheese,
        main_topping: selectedMainTopping,
        extra_toppings: selectedExtraToppings,
      });

      if (response.data.success) {
        navigate(`/orders/${response.data.order_id}`);
      }
    } catch (error) {
      console.error('Failed to create order:', error);
      alert('Failed to create order. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setSelectedSauce('');
    setSelectedCheese('');
    setSelectedMainTopping('');
    setSelectedExtraToppings([]);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!menuData) {
    return <div className="text-center text-red-600">Failed to load menu</div>;
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">Customize Your Pizza</h1>
        <p className="text-gray-600">Build your perfect pizza with our fresh ingredients</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Sauce */}
          <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow duration-300">
            <div className="bg-gray-200 px-4 py-3">
              <h3 className="font-semibold text-gray-900">Sauce</h3>
            </div>
            <div className="p-4 space-y-3">
              {menuData.sauces.map((sauce) => (
                <label key={sauce} className="flex items-center space-x-3 cursor-pointer group">
                  <input
                    type="radio"
                    name="sauce"
                    value={sauce}
                    checked={selectedSauce === sauce}
                    onChange={(e) => setSelectedSauce(e.target.value)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                    required
                  />
                  <span className="text-gray-700 group-hover:text-blue-600 transition-colors">
                    {sauce}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Cheese */}
          <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow duration-300">
            <div className="bg-gray-300 px-4 py-3">
              <h3 className="font-semibold text-gray-900">Cheese</h3>
            </div>
            <div className="p-4 space-y-3">
              {menuData.cheeses.map((cheese) => (
                <label key={cheese} className="flex items-center space-x-3 cursor-pointer group">
                  <input
                    type="radio"
                    name="cheese"
                    value={cheese}
                    checked={selectedCheese === cheese}
                    onChange={(e) => setSelectedCheese(e.target.value)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                    required
                  />
                  <span className="text-gray-700 group-hover:text-blue-600 transition-colors">
                    {cheese}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Main Topping */}
          <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow duration-300">
            <div className="bg-gray-500 text-white px-4 py-3">
              <h3 className="font-semibold">Main topping</h3>
            </div>
            <div className="p-4 space-y-3">
              {menuData.main_toppings.map((topping) => (
                <label key={topping} className="flex items-center space-x-3 cursor-pointer group">
                  <input
                    type="radio"
                    name="main_topping"
                    value={topping}
                    checked={selectedMainTopping === topping}
                    onChange={(e) => setSelectedMainTopping(e.target.value)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                    required
                  />
                  <span className="text-gray-700 group-hover:text-blue-600 transition-colors">
                    {topping}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Extra Toppings */}
          <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-xl transition-shadow duration-300">
            <div className="bg-gray-700 text-white px-4 py-3">
              <h3 className="font-semibold">Extra toppings</h3>
            </div>
            <div className="p-4 space-y-3">
              {menuData.extra_toppings.map((topping) => (
                <label key={topping} className="flex items-center space-x-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    value={topping}
                    checked={selectedExtraToppings.includes(topping)}
                    onChange={() => handleExtraToppingToggle(topping)}
                    className="h-4 w-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <span className="text-gray-700 group-hover:text-blue-600 transition-colors">
                    {topping}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={submitting}
            className="px-8 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transform transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            {submitting ? 'Submitting...' : 'Submit your order'}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="px-8 py-3 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transform transition-all duration-200 hover:scale-105"
          >
            Clear form
          </button>
        </div>
      </form>
    </div>
  );
};

export default Menu;
