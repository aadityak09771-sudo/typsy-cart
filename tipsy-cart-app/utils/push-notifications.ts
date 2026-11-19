
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';

const PUSH_TOKEN_API =
  'https://tipsy-cart.onrender.com/accounts/api/push-token/';

export async function registerForPushNotifications(
  authToken: string
): Promise<boolean> {
  try {
    console.log('PUSH DEBUG: Function started');
    console.log('PUSH DEBUG: Auth token exists:', !!authToken);
    console.log('PUSH DEBUG: Physical device:', Device.isDevice);

    if (!authToken || !Device.isDevice) {
      console.log('PUSH DEBUG: Missing auth token or physical device');
      return false;
    }

    // Android notification channel
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Tipsy Cart Notifications',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#D63384',
      });
    }

    console.log('PUSH DEBUG: Checking notification permission');

    // Check notification permission
    let permission = await Notifications.getPermissionsAsync();

    if (!permission.granted) {
      permission = await Notifications.requestPermissionsAsync();
    }

    console.log('PUSH DEBUG: Permission granted:', permission.granted);

    if (!permission.granted) {
      console.log('PUSH DEBUG: Notification permission denied');
      return false;
    }

    // Get Expo project ID
    const projectId =
      Constants.expoConfig?.extra?.eas?.projectId ??
      Constants.easConfig?.projectId;

    console.log('PUSH DEBUG: Project ID:', projectId);

    if (!projectId) {
      console.warn('PUSH DEBUG: Expo project ID is missing');
      return false;
    }

    // Generate Expo Push Token
    console.log('PUSH DEBUG: Generating Expo Push Token');

    const pushTokenResponse =
      await Notifications.getExpoPushTokenAsync({
        projectId,
      });

    const expoPushToken = pushTokenResponse.data;

    console.log('PUSH DEBUG: Push token generated:', !!expoPushToken);

    if (!expoPushToken) {
      console.warn('PUSH DEBUG: Push token is empty');
      return false;
    }

    // Register token with Django backend
    console.log('PUSH DEBUG: Sending token to Django backend');

    const response = await fetch(PUSH_TOKEN_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Authorization: `Token ${authToken}`,
      },
      body: JSON.stringify({
        expo_push_token: expoPushToken,
        platform: Platform.OS,
      }),
    });

    console.log('PUSH DEBUG: Backend HTTP status:', response.status);

    const data = await response.json();

    console.log('PUSH DEBUG: Backend response:', data);

    if (!response.ok || !data.success) {
      console.warn(
        'PUSH DEBUG: Token registration failed:',
        data.message || response.status
      );
      return false;
    }

    console.log(
      'Tipsy Cart push notification registered successfully.'
    );

    return true;
  } catch (error) {
    console.warn('PUSH DEBUG: Notification setup error:', error);
    return false;
  }
}
