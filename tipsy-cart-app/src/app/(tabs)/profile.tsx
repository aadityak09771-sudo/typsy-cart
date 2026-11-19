
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useFocusEffect, useRouter } from 'expo-router';

const API_BASE = 'https://tipsy-cart.onrender.com/accounts/api';

const TOKEN_KEY = '@tipsy_cart_auth_token_v1';
const USER_KEY = '@tipsy_cart_auth_user_v1';

type User = {
  id?: number;
  username: string;
  email: string;
};

export default function ProfileScreen() {
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [loggingOut, setLoggingOut] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);

      const savedToken = await AsyncStorage.getItem(TOKEN_KEY);
      const savedUser = await AsyncStorage.getItem(USER_KEY);

      setToken(savedToken);

      if (!savedToken) {
        setUser(null);
        return;
      }

      if (savedUser) {
        setUser(JSON.parse(savedUser));
      }

      const response = await fetch(`${API_BASE}/profile/`, {
        method: 'GET',
        headers: {
          Authorization: `Token ${savedToken}`,
          Accept: 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        if (response.status === 401) {
          await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);
          setToken(null);
          setUser(null);
          return;
        }

        throw new Error(data.error || 'Profile load nahi ho paya.');
      }

      setUser(data.user);
      await AsyncStorage.setItem(USER_KEY, JSON.stringify(data.user));
    } catch (error) {
      console.log('Profile error:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadProfile();
    }, [loadProfile])
  );

  const handleLogout = async () => {
    Alert.alert(
      'Logout',
      'Kya aap Tipsy Cart se logout karna chahte hain?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: async () => {
            try {
              setLoggingOut(true);

              const savedToken = await AsyncStorage.getItem(TOKEN_KEY);

              if (savedToken) {
                await fetch(`${API_BASE}/logout/`, {
                  method: 'POST',
                  headers: {
                    Authorization: `Token ${savedToken}`,
                    Accept: 'application/json',
                  },
                });
              }

              await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);

              setToken(null);
              setUser(null);

              Alert.alert('Success', 'Aap logout ho gaye hain.');
            } catch {
              Alert.alert(
                'Error',
                'Logout complete nahi ho paya. Internet check karein.'
              );
            } finally {
              setLoggingOut(false);
            }
          },
        },
      ]
    );
  };

  const goToOrders = () => {
    router.push('/orders');
  };

  const goToAddresses = () => {
    router.push('/addresses');
  };

  const comingSoon = (feature: string) => {
    Alert.alert(
      feature,
      `${feature} feature Tipsy Cart mein jald hi available hoga. ❤️`
    );
  };

  const showAbout = () => {
    Alert.alert(
      'About Tipsy Cart',
      'Care • Comfort • Confidence\n\nTipsy Cart – Shopping that cares for you. ❤️'
    );
  };

  const showHelp = () => {
    Alert.alert(
      'Help & Support',
      'Aapko kisi bhi help ki zaroorat ho toh Tipsy Cart support team se contact karein. Support contact details jald add hongi.'
    );
  };

  const MenuItem = ({
    emoji,
    title,
    subtitle,
    onPress,
  }: {
    emoji: string;
    title: string;
    subtitle: string;
    onPress: () => void;
  }) => (
    <Pressable style={styles.menuItem} onPress={onPress}>
      <View style={styles.menuIcon}>
        <Text style={styles.menuEmoji}>{emoji}</Text>
      </View>

      <View style={styles.menuTextContainer}>
        <Text style={styles.menuTitle}>{title}</Text>
        <Text style={styles.menuSubtitle}>{subtitle}</Text>
      </View>

      <Text style={styles.arrow}>›</Text>
    </Pressable>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator size="large" color="#D63384" />
        <Text style={styles.loadingText}>Loading account...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Text style={styles.brand}>Tipsy Cart</Text>
          <Text style={styles.tagline}>
            CARE • COMFORT • CONFIDENCE
          </Text>
        </View>

        <View style={styles.profileCard}>
          <Text style={styles.heading}>My Account</Text>

          {token && user ? (
            <>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>
                  {user.username?.charAt(0)?.toUpperCase() || 'U'}
                </Text>
              </View>

              <Text style={styles.username}>{user.username}</Text>
              <Text style={styles.email}>{user.email}</Text>

              <Pressable style={styles.primaryButton} onPress={goToOrders}>
                <Text style={styles.primaryButtonText}>📦  My Orders</Text>
              </Pressable>

              <Pressable
                style={styles.secondaryButton}
                onPress={() => router.push('/login')}
              >
                <Text style={styles.secondaryButtonText}>
                  Switch Account
                </Text>
              </Pressable>
            </>
          ) : (
            <>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>👤</Text>
              </View>

              <Text style={styles.welcome}>Welcome to Tipsy Cart!</Text>

              <Text style={styles.description}>
                Login ya register karke apne orders aur account ko manage karein.
              </Text>

              <Pressable
                style={styles.primaryButton}
                onPress={() => router.push('/login')}
              >
                <Text style={styles.primaryButtonText}>Login</Text>
              </Pressable>

              <Pressable
                style={styles.secondaryButton}
                onPress={() => router.push('/register')}
              >
                <Text style={styles.secondaryButtonText}>
                  Create New Account
                </Text>
              </Pressable>
            </>
          )}
        </View>

        <Text style={styles.sectionTitle}>Your Services</Text>

        <View style={styles.menuCard}>
          <MenuItem
            emoji="📍"
            title="Saved Addresses"
            subtitle="Manage your delivery addresses"
            onPress={goToAddresses}
          />

          <View style={styles.separator} />

          <MenuItem
            emoji="❤️"
            title="Wishlist"
            subtitle="Your favourite products"
            onPress={() => comingSoon('Wishlist')}
          />

          <View style={styles.separator} />

          <MenuItem
            emoji="🎧"
            title="Help & Support"
            subtitle="We are here to help you"
            onPress={showHelp}
          />

          <View style={styles.separator} />

          <MenuItem
            emoji="ℹ️"
            title="About Tipsy Cart"
            subtitle="Know more about our brand"
            onPress={showAbout}
          />
        </View>

        {token && user && (
          <Pressable
            style={styles.logoutButton}
            onPress={handleLogout}
            disabled={loggingOut}
          >
            <Text style={styles.logoutText}>
              {loggingOut ? 'Logging out...' : '🚪  Logout'}
            </Text>
          </Pressable>
        )}

        <Text style={styles.footer}>
          Shopping that cares for you. ❤️
        </Text>
        <Text style={styles.version}>Tipsy Cart • Version 1.0.0</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFF7FA',
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#FFF7FA',
  },
  loadingText: {
    marginTop: 12,
    color: '#777',
  },
  content: {
    padding: 20,
    paddingBottom: 35,
    flexGrow: 1,
  },
  header: {
    alignItems: 'center',
    marginTop: 18,
    marginBottom: 25,
  },
  brand: {
    fontSize: 31,
    fontWeight: '900',
    color: '#D63384',
  },
  tagline: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.5,
    color: '#9B7186',
    marginTop: 6,
  },
  profileCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    padding: 23,
    borderWidth: 1,
    borderColor: '#F3DFE9',
    elevation: 3,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 10,
  },
  heading: {
    fontSize: 22,
    fontWeight: '900',
    color: '#29202A',
    textAlign: 'center',
    marginBottom: 22,
  },
  avatar: {
    width: 82,
    height: 82,
    borderRadius: 41,
    backgroundColor: '#FCE0ED',
    alignSelf: 'center',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 14,
  },
  avatarText: {
    fontSize: 34,
    fontWeight: '900',
    color: '#D63384',
  },
  username: {
    fontSize: 21,
    fontWeight: '900',
    color: '#29202A',
    textAlign: 'center',
  },
  email: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    marginTop: 5,
    marginBottom: 18,
  },
  welcome: {
    fontSize: 19,
    fontWeight: '800',
    color: '#29202A',
    textAlign: 'center',
  },
  description: {
    fontSize: 14,
    lineHeight: 22,
    color: '#777',
    textAlign: 'center',
    marginTop: 10,
    marginBottom: 15,
  },
  primaryButton: {
    backgroundColor: '#D63384',
    padding: 15,
    borderRadius: 13,
    alignItems: 'center',
    marginTop: 10,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
  },
  secondaryButton: {
    backgroundColor: '#FCE0ED',
    padding: 15,
    borderRadius: 13,
    alignItems: 'center',
    marginTop: 12,
  },
  secondaryButtonText: {
    color: '#B51F68',
    fontSize: 15,
    fontWeight: '800',
  },
  sectionTitle: {
    fontSize: 19,
    fontWeight: '900',
    color: '#29202A',
    marginTop: 27,
    marginBottom: 13,
    marginLeft: 3,
  },
  menuCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    paddingHorizontal: 15,
    borderWidth: 1,
    borderColor: '#F3DFE9',
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 8,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 16,
  },
  menuIcon: {
    width: 43,
    height: 43,
    borderRadius: 13,
    backgroundColor: '#FFF0F6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  menuEmoji: {
    fontSize: 21,
  },
  menuTextContainer: {
    flex: 1,
    marginLeft: 13,
  },
  menuTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: '#302430',
  },
  menuSubtitle: {
    fontSize: 12,
    color: '#999',
    marginTop: 4,
  },
  arrow: {
    fontSize: 27,
    color: '#C78BA8',
    marginLeft: 8,
  },
  separator: {
    height: 1,
    backgroundColor: '#F5E8EE',
  },
  logoutButton: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#F3D5DF',
    padding: 16,
    borderRadius: 14,
    alignItems: 'center',
    marginTop: 20,
  },
  logoutText: {
    color: '#D32F2F',
    fontWeight: '800',
    fontSize: 15,
  },
  footer: {
    textAlign: 'center',
    color: '#A36F88',
    marginTop: 27,
    fontWeight: '700',
  },
  version: {
    textAlign: 'center',
    color: '#B5A1AB',
    fontSize: 11,
    marginTop: 8,
  },
});
