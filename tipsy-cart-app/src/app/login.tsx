
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import { registerForPushNotifications } from '../../utils/push-notifications';

const API_URL = 'https://tipsy-cart.onrender.com/accounts/api/login/';

const TOKEN_KEY = '@tipsy_cart_auth_token_v1';
const USER_KEY = '@tipsy_cart_auth_user_v1';

export default function LoginScreen() {
  const router = useRouter();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!username.trim() || !password) {
      Alert.alert('Required', 'Username aur password enter karein.');
      return;
    }

    try {
      setLoading(true);

      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        Alert.alert(
          'Login Failed',
          data.error || data.message || 'Username ya password galat hai.'
        );
        return;
      }

      await AsyncStorage.setItem(TOKEN_KEY, data.token);
      await AsyncStorage.setItem(USER_KEY, JSON.stringify(data.user));

      // Register device for push notifications
      await registerForPushNotifications(data.token);

      Alert.alert('Success', 'Welcome to Tipsy Cart!', [
        {
          text: 'Continue',
          onPress: () => router.replace('/profile'),
        },
      ]);
    } catch (error) {
      Alert.alert(
        'Connection Error',
        'Server se connect nahi ho paya. Internet check karein.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.keyboard}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.card}>
          <Text style={styles.brand}>Tipsy Cart</Text>
          <Text style={styles.tagline}>Care • Comfort • Confidence</Text>

          <Text style={styles.heading}>Welcome Back!</Text>
          <Text style={styles.subtitle}>Login to your account</Text>

          <Text style={styles.label}>Username</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter username"
            placeholderTextColor="#999"
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
            editable={!loading}
          />

          <Text style={styles.label}>Password</Text>
          <TextInput
            style={styles.input}
            placeholder="Enter password"
            placeholderTextColor="#999"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            editable={!loading}
          />

          <Pressable
            style={[styles.button, loading && styles.disabledButton]}
            onPress={handleLogin}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.buttonText}>Login</Text>
            )}
          </Pressable>

          <View style={styles.footerRow}>
            <Text style={styles.footerText}>Don't have an account?</Text>
            <Pressable
              onPress={() => router.push('/register')}
              disabled={loading}
            >
              <Text style={styles.link}> Register</Text>
            </Pressable>
          </View>

          <Pressable
            onPress={() => router.replace('/profile')}
            style={styles.backButton}
            disabled={loading}
          >
            <Text style={styles.backText}>Back to Account</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFF7FA',
  },
  keyboard: {
    flex: 1,
    justifyContent: 'center',
    padding: 22,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    padding: 24,
    elevation: 4,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 12,
  },
  brand: {
    fontSize: 30,
    fontWeight: '900',
    color: '#D63384',
    textAlign: 'center',
  },
  tagline: {
    color: '#888',
    textAlign: 'center',
    marginTop: 5,
    marginBottom: 28,
  },
  heading: {
    fontSize: 25,
    fontWeight: '800',
    color: '#29202A',
  },
  subtitle: {
    color: '#888',
    marginTop: 5,
    marginBottom: 25,
  },
  label: {
    fontWeight: '700',
    color: '#29202A',
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#FFF7FA',
    borderWidth: 1,
    borderColor: '#F0D5E2',
    borderRadius: 12,
    padding: 15,
    fontSize: 15,
    color: '#29202A',
  },
  button: {
    backgroundColor: '#D63384',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 25,
  },
  disabledButton: {
    opacity: 0.65,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 22,
  },
  footerText: {
    color: '#777',
  },
  link: {
    color: '#D63384',
    fontWeight: '800',
  },
  backButton: {
    alignItems: 'center',
    marginTop: 22,
  },
  backText: {
    color: '#777',
    fontWeight: '600',
  },
});
