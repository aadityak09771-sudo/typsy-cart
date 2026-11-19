
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useFocusEffect, useRouter } from 'expo-router';

const API_URL = 'https://tipsy-cart.onrender.com/accounts/api/my-orders/';
const TOKEN_KEY = '@tipsy_cart_auth_token_v1';

type OrderItem = {
  product_name: string;
  price: string;
  quantity: number;
  subtotal: string;
};

type Order = {
  id: number;
  total_amount: string;
  status: string;
  payment_method: string;
  created_at: string;
  full_name?: string;
  phone?: string;
  address?: string;
  city?: string;
  state?: string;
  pincode?: string;
  items: OrderItem[];
};

const TRACKING_STEPS = [
  'Pending',
  'Confirmed',
  'Shipped',
  'Delivered',
];

export default function OrdersScreen() {
  const router = useRouter();

  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [expandedOrders, setExpandedOrders] = useState<
    Record<number, boolean>
  >({});

  const loadOrders = useCallback(async () => {
    try {
      setError('');

      const token = await AsyncStorage.getItem(TOKEN_KEY);

      if (!token) {
        setOrders([]);
        setError('Please login to view your orders.');
        return;
      }

      const response = await fetch(API_URL, {
        method: 'GET',
        headers: {
          Authorization: `Token ${token}`,
          Accept: 'application/json',
        },
      });

      const data = await response.json();

      if (response.status === 401) {
        setOrders([]);
        setError('Your session has expired. Please login again.');
        return;
      }

      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Orders load nahi ho paye.');
      }

      setOrders(data.orders || []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Something went wrong.'
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      loadOrders();
    }, [loadOrders])
  );

  const onRefresh = () => {
    setRefreshing(true);
    loadOrders();
  };

  const toggleDetails = (orderId: number) => {
    setExpandedOrders((previous) => ({
      ...previous,
      [orderId]: !previous[orderId],
    }));
  };

  const formatDate = (date: string) => {
    const parsed = new Date(date);

    if (Number.isNaN(parsed.getTime())) return date;

    return parsed.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Delivered':
        return {
          color: '#16834A',
          backgroundColor: '#E6F6EC',
        };
      case 'Cancelled':
        return {
          color: '#C62828',
          backgroundColor: '#FDEAEA',
        };
      case 'Shipped':
        return {
          color: '#1769AA',
          backgroundColor: '#E7F1FC',
        };
      case 'Confirmed':
        return {
          color: '#8A6100',
          backgroundColor: '#FFF3D6',
        };
      default:
        return {
          color: '#A65B00',
          backgroundColor: '#FFF0DC',
        };
    }
  };

  const getPaymentLabel = (method: string) => {
    switch (method) {
      case 'COD':
        return 'Cash on Delivery';
      case 'UPI':
        return 'UPI / Online Payment';
      case 'Pending':
        return 'Payment Pending';
      default:
        return method || 'Not specified';
    }
  };

  const renderTracking = (status: string) => {
    if (status === 'Cancelled') {
      return (
        <View style={styles.cancelledBox}>
          <Text style={styles.cancelledTitle}>
            ✕ Order Cancelled
          </Text>
          <Text style={styles.cancelledText}>
            This order has been cancelled.
          </Text>
        </View>
      );
    }

    const currentIndex = TRACKING_STEPS.indexOf(status);

    return (
      <View style={styles.trackingContainer}>
        {TRACKING_STEPS.map((step, index) => {
          const completed = currentIndex >= index;
          const isCurrent = currentIndex === index;

          return (
            <View key={step} style={styles.trackingStep}>
              <View style={styles.timelineColumn}>
                <View
                  style={[
                    styles.timelineCircle,
                    completed && styles.timelineCircleActive,
                    isCurrent && styles.timelineCircleCurrent,
                  ]}
                >
                  <Text
                    style={[
                      styles.timelineCheck,
                      completed && styles.timelineCheckActive,
                    ]}
                  >
                    {completed ? '✓' : ''}
                  </Text>
                </View>

                {index !== TRACKING_STEPS.length - 1 && (
                  <View
                    style={[
                      styles.timelineLine,
                      currentIndex > index &&
                        styles.timelineLineActive,
                    ]}
                  />
                )}
              </View>

              <View style={styles.trackingTextContainer}>
                <Text
                  style={[
                    styles.trackingLabel,
                    completed && styles.trackingLabelActive,
                  ]}
                >
                  {step}
                </Text>

                {isCurrent && (
                  <Text style={styles.currentStatus}>
                    Current order status
                  </Text>
                )}
              </View>
            </View>
          );
        })}

        {currentIndex === -1 && (
          <Text style={styles.unknownStatus}>
            Current status: {status}
          </Text>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.back}>‹ Back</Text>
        </Pressable>

        <Text style={styles.title}>My Orders</Text>

        <View style={{ width: 50 }} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#D63384" />
          <Text style={styles.muted}>Loading your orders...</Text>
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.emptyIcon}>📦</Text>
          <Text style={styles.emptyTitle}>
            Unable to load orders
          </Text>
          <Text style={styles.muted}>{error}</Text>

          <Pressable
            style={styles.button}
            onPress={() => router.push('/login')}
          >
            <Text style={styles.buttonText}>Login</Text>
          </Pressable>

          <Pressable
            style={styles.retryButton}
            onPress={onRefresh}
          >
            <Text style={styles.retryText}>Try Again</Text>
          </Pressable>
        </View>
      ) : orders.length === 0 ? (
        <ScrollView
          contentContainerStyle={styles.center}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
            />
          }
        >
          <Text style={styles.emptyIcon}>🛍️</Text>
          <Text style={styles.emptyTitle}>No Orders Yet</Text>

          <Text style={styles.muted}>
            Your orders will appear here after you place an order
            while logged in.
          </Text>

          <Pressable
            style={styles.button}
            onPress={() => router.replace('/' as any)}
          >
            <Text style={styles.buttonText}>Start Shopping</Text>
          </Pressable>
        </ScrollView>
      ) : (
        <ScrollView
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
            />
          }
        >
          <Text style={styles.count}>
            {orders.length} order{orders.length !== 1 ? 's' : ''} found
          </Text>

          {orders.map((order) => {
            const expanded = !!expandedOrders[order.id];
            const statusStyle = getStatusColor(order.status);

            return (
              <View key={order.id} style={styles.orderCard}>
                <View style={styles.orderTop}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.orderId}>
                      Order #{order.id}
                    </Text>

                    <Text style={styles.date}>
                      {formatDate(order.created_at)}
                    </Text>
                  </View>

                  <Text
                    style={[
                      styles.status,
                      statusStyle,
                    ]}
                  >
                    {order.status}
                  </Text>
                </View>

                <View style={styles.divider} />

                {order.items?.map((item, index) => (
                  <View
                    key={`${order.id}-${index}`}
                    style={styles.itemRow}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={styles.productName}>
                        {item.product_name}
                      </Text>

                      <Text style={styles.itemDetails}>
                        ₹{item.price} × {item.quantity}
                      </Text>
                    </View>

                    <Text style={styles.itemPrice}>
                      ₹{item.subtotal}
                    </Text>
                  </View>
                ))}

                <View style={styles.divider} />

                <View style={styles.totalRow}>
                  <Text style={styles.totalLabel}>
                    Payment
                  </Text>

                  <Text style={styles.payment}>
                    {getPaymentLabel(order.payment_method)}
                  </Text>
                </View>

                <View style={styles.totalRow}>
                  <Text style={styles.totalLabel}>
                    Total Amount
                  </Text>

                  <Text style={styles.total}>
                    ₹{order.total_amount}
                  </Text>
                </View>

                <Pressable
                  style={styles.detailsButton}
                  onPress={() => toggleDetails(order.id)}
                >
                  <Text style={styles.detailsButtonText}>
                    {expanded ? 'Hide Details' : 'View Details'}
                  </Text>

                  <Text style={styles.arrow}>
                    {expanded ? '⌃' : '⌄'}
                  </Text>
                </Pressable>

                {expanded && (
                  <View style={styles.detailsContainer}>
                    <View style={styles.divider} />

                    <Text style={styles.sectionTitle}>
                      📍 Delivery Details
                    </Text>

                    <Text style={styles.detailLabel}>
                      Customer Name
                    </Text>
                    <Text style={styles.detailValue}>
                      {order.full_name || 'Not available'}
                    </Text>

                    <Text style={styles.detailLabel}>
                      Phone Number
                    </Text>
                    <Text style={styles.detailValue}>
                      {order.phone || 'Not available'}
                    </Text>

                    <Text style={styles.detailLabel}>
                      Delivery Address
                    </Text>
                    <Text style={styles.detailValue}>
                      {[
                        order.address,
                        order.city,
                        order.state,
                        order.pincode,
                      ]
                        .filter(Boolean)
                        .join(', ') || 'Not available'}
                    </Text>

                    <View style={styles.divider} />

                    <Text style={styles.sectionTitle}>
                      🚚 Track Your Order
                    </Text>

                    {renderTracking(order.status)}

                    <View style={styles.divider} />

                    <Text style={styles.sectionTitle}>
                      💳 Payment Summary
                    </Text>

                    <View style={styles.totalRow}>
                      <Text style={styles.totalLabel}>
                        Payment Method
                      </Text>
                      <Text style={styles.payment}>
                        {getPaymentLabel(order.payment_method)}
                      </Text>
                    </View>

                    <View style={styles.totalRow}>
                      <Text style={styles.totalLabel}>
                        Order Total
                      </Text>
                      <Text style={styles.total}>
                        ₹{order.total_amount}
                      </Text>
                    </View>
                  </View>
                )}
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFF7FA',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 18,
    backgroundColor: '#FFFFFF',
  },
  back: {
    color: '#D63384',
    fontSize: 17,
    fontWeight: '700',
  },
  title: {
    fontSize: 21,
    fontWeight: '900',
    color: '#29202A',
  },
  center: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 25,
  },
  muted: {
    color: '#888',
    textAlign: 'center',
    marginTop: 10,
    lineHeight: 21,
  },
  emptyIcon: {
    fontSize: 55,
    marginBottom: 15,
  },
  emptyTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#29202A',
  },
  button: {
    backgroundColor: '#D63384',
    paddingHorizontal: 25,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 22,
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 15,
  },
  retryButton: {
    padding: 15,
  },
  retryText: {
    color: '#D63384',
    fontWeight: '700',
  },
  list: {
    padding: 16,
    paddingBottom: 30,
  },
  count: {
    fontSize: 15,
    fontWeight: '700',
    color: '#777',
    marginBottom: 15,
  },
  orderCard: {
    backgroundColor: '#FFFFFF',
    padding: 17,
    borderRadius: 17,
    marginBottom: 16,
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 8,
  },
  orderTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderId: {
    fontSize: 17,
    fontWeight: '900',
    color: '#29202A',
  },
  date: {
    color: '#888',
    fontSize: 12,
    marginTop: 5,
  },
  status: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
    fontSize: 12,
    fontWeight: '800',
    overflow: 'hidden',
  },
  divider: {
    height: 1,
    backgroundColor: '#F0E6EC',
    marginVertical: 14,
  },
  itemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginVertical: 7,
  },
  productName: {
    color: '#29202A',
    fontWeight: '700',
    fontSize: 14,
  },
  itemDetails: {
    color: '#888',
    fontSize: 12,
    marginTop: 4,
  },
  itemPrice: {
    color: '#29202A',
    fontWeight: '700',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 9,
    gap: 10,
  },
  totalLabel: {
    color: '#777',
    fontWeight: '600',
    flexShrink: 1,
  },
  payment: {
    color: '#29202A',
    fontWeight: '700',
    textAlign: 'right',
    flexShrink: 1,
  },
  total: {
    color: '#D63384',
    fontSize: 18,
    fontWeight: '900',
  },
  detailsButton: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#FFF0F6',
    padding: 13,
    borderRadius: 11,
    marginTop: 17,
  },
  detailsButtonText: {
    color: '#D63384',
    fontWeight: '800',
    fontSize: 14,
  },
  arrow: {
    color: '#D63384',
    fontSize: 19,
    fontWeight: '900',
    marginLeft: 8,
  },
  detailsContainer: {
    marginTop: 3,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '900',
    color: '#29202A',
    marginBottom: 13,
  },
  detailLabel: {
    color: '#888',
    fontSize: 12,
    fontWeight: '600',
    marginTop: 10,
  },
  detailValue: {
    color: '#29202A',
    fontSize: 14,
    fontWeight: '600',
    marginTop: 4,
    lineHeight: 21,
  },
  trackingContainer: {
    marginTop: 5,
    marginBottom: 8,
  },
  trackingStep: {
    flexDirection: 'row',
    minHeight: 55,
  },
  timelineColumn: {
    width: 28,
    alignItems: 'center',
  },
  timelineCircle: {
    width: 23,
    height: 23,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#D9CDD3',
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1,
  },
  timelineCircleActive: {
    borderColor: '#D63384',
    backgroundColor: '#D63384',
  },
  timelineCircleCurrent: {
    borderWidth: 3,
  },
  timelineCheck: {
    fontSize: 12,
    color: '#FFFFFF',
    fontWeight: '900',
  },
  timelineCheckActive: {
    color: '#FFFFFF',
  },
  timelineLine: {
    width: 2,
    flex: 1,
    backgroundColor: '#E7DDE2',
  },
  timelineLineActive: {
    backgroundColor: '#D63384',
  },
  trackingTextContainer: {
    paddingLeft: 12,
    paddingTop: 2,
    flex: 1,
  },
  trackingLabel: {
    color: '#999',
    fontSize: 14,
    fontWeight: '600',
  },
  trackingLabelActive: {
    color: '#29202A',
    fontWeight: '800',
  },
  currentStatus: {
    color: '#D63384',
    fontSize: 11,
    marginTop: 4,
    fontWeight: '700',
  },
  cancelledBox: {
    backgroundColor: '#FDEAEA',
    padding: 14,
    borderRadius: 12,
  },
  cancelledTitle: {
    color: '#C62828',
    fontSize: 15,
    fontWeight: '900',
  },
  cancelledText: {
    color: '#8D3333',
    fontSize: 12,
    marginTop: 5,
  },
  unknownStatus: {
    color: '#A65B00',
    fontWeight: '700',
    fontSize: 13,
  },
});
