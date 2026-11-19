
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import { registerForPushNotifications } from '../../utils/push-notifications';

const API_URL = 'https://tipsy-cart.onrender.com/accounts/api/register/';

const TOKEN_KEY = '@tipsy_cart_auth_token_v1';
const USER_KEY = '@tipsy_cart_auth_user_v1';

export default function RegisterScreen() {
  const router = useRouter();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    const cleanUsername = username.trim();
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanUsername || !cleanEmail || !password || !confirmPassword) {
      Alert.alert('Required', 'Saari details fill karein.');
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      Alert.alert('Invalid Email', 'Valid email enter karein.');
      return;
    }

    if (password.length < 8) {
      Alert.alert(
        'Weak Password',
        'Password minimum 8 characters ka hona chahiye.'
      );
      return;
    }

    if (password !== confirmPassword) {
      Alert.alert('Password Error', 'Dono passwords match nahi kar rahe.');
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
          username: cleanUsername,
          email: cleanEmail,
          password: password,
        }),
      });

      const responseText = await response.text();

      let data: any = {};

      try {
        data = responseText ? JSON.parse(responseText) : {};
      } catch {
        data = {};
      }

      const token = data.token || data.key;
      const user = data.user;

      if (!response.ok || data.success === false || !token || !user) {
        Alert.alert(
          `Registration Failed (HTTP ${response.status})`,
          `Server response:\n${responseText || 'Empty response'}`
        );
        return;
      }

      await AsyncStorage.setItem(TOKEN_KEY, token);
      await AsyncStorage.setItem(USER_KEY, JSON.stringify(user));

      // Register device for push notifications
      await registerForPushNotifications(token);

      Alert.alert(
        'Account Created',
        'Welcome to Tipsy Cart!',
        [
          {
            text: 'Continue',
            onPress: () => router.replace('/profile'),
          },
        ]
      );
    } catch (error: any) {
      Alert.alert(
        'Connection Error',
        error?.message ||
          'Server se connect nahi ho paya. Internet check karein aur dobara try karein.'
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
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.card}>
            <Text style={styles.brand}>Tipsy Cart</Text>

            <Text style={styles.tagline}>
              Care • Comfort • Confidence
            </Text>

            <Text style={styles.heading}>Create Account</Text>

            <Text style={styles.subtitle}>
              Join Tipsy Cart today!
            </Text>

            <Text style={styles.label}>Username</Text>
            <TextInput
              style={styles.input}
              placeholder="Choose username"
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              autoCorrect={false}
              editable={!loading}
            />

            <Text style={styles.label}>Email Address</Text>
            <TextInput
              style={styles.input}
              placeholder="Enter email"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              editable={!loading}
            />

            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              placeholder="Minimum 8 characters"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              editable={!loading}
            />

            <Text style={styles.label}>Confirm Password</Text>
            <TextInput
              style={styles.input}
              placeholder="Re-enter password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
              editable={!loading}
            />

            <Pressable
              style={[
                styles.button,
                loading && styles.disabledButton,
              ]}
              onPress={handleRegister}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.buttonText}>
                  Create Account
                </Text>
              )}
            </Pressable>

            <View style={styles.footerRow}>
              <Text style={styles.footerText}>
                Already have an account?
              </Text>

              <Pressable
                onPress={() => router.push('/login')}
                disabled={loading}
              >
                <Text style={styles.link}> Login</Text>
              </Pressable>
            </View>

            <Pressable
              onPress={() => router.replace('/profile')}
              style={styles.backButton}
              disabled={loading}
            >
              <Text style={styles.backText}>
                Back to Account
              </Text>
            </Pressable>
          </View>
        </ScrollView>
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
  },
  scroll: {
    flexGrow: 1,
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
    marginBottom: 25,
  },
  heading: {
    fontSize: 25,
    fontWeight: '800',
    color: '#29202A',
  },
  subtitle: {
    color: '#888',
    marginTop: 5,
    marginBottom: 20,
  },
  label: {
    fontWeight: '700',
    color: '#29202A',
    marginBottom: 8,
    marginTop: 13,
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
