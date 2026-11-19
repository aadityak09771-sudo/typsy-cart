
import React from 'react';
import {
  ScrollView,
  StyleSheet,
  Text,
  View,
  Pressable,
  StatusBar,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';

const COLORS = {
  background: '#FFF8FA',
  primary: '#D63384',
  dark: '#25212A',
  muted: '#817984',
  white: '#FFFFFF',
  lightPink: '#FCE4EF',
  border: '#F2E5EC',
};

const categories = [
  {
    emoji: '🌸',
    title: "Women's Care",
    subtitle: 'Care & comfort',
    color: '#FCE4EF',
  },
  {
    emoji: '🛡️',
    title: 'Safety Essentials',
    subtitle: 'Safety first',
    color: '#E9E8FF',
  },
  {
    emoji: '🧴',
    title: 'Personal Care',
    subtitle: 'Everyday beauty',
    color: '#FCEEDC',
  },
  {
    emoji: '🛍️',
    title: 'Daily Essentials',
    subtitle: 'Everyday needs',
    color: '#E4F4ED',
  },
  {
    emoji: '🥑',
    title: 'Groceries',
    subtitle: 'Coming soon',
    color: '#E8F2DF',
  },
  {
    emoji: '✨',
    title: 'Beauty & Skincare',
    subtitle: 'Feel your best',
    color: '#F0E5FA',
  },
];

const collections = [
  {
    emoji: '🔥',
    title: 'Trending Now',
    description: 'Popular picks everyone loves',
    color: '#FFF0E5',
  },
  {
    emoji: '🆕',
    title: 'New Arrivals',
    description: 'Discover something new',
    color: '#E9F2FF',
  },
  {
    emoji: '🎁',
    title: 'Special Offers',
    description: 'Explore exciting deals',
    color: '#FCE4EF',
  },
];

export default function ExploreScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const goToHome = () => {
    router.navigate('/(tabs)');
  };

  return (
    <View style={styles.screen}>
      <StatusBar barStyle="dark-content" />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingTop: insets.top + 12, paddingBottom: 110 },
        ]}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>TIPSY CART</Text>
            <Text style={styles.heading}>Explore</Text>
            <Text style={styles.subheading}>
              Discover products made for everyday life.
            </Text>
          </View>

          <View style={styles.headerIcon}>
            <Text style={styles.headerEmoji}>🛍️</Text>
          </View>
        </View>

        {/* Search-style banner */}
        <Pressable style={styles.searchBanner} onPress={goToHome}>
          <Text style={styles.searchIcon}>🔍</Text>
          <Text style={styles.searchText}>Find your everyday essentials</Text>
          <Text style={styles.searchArrow}>›</Text>
        </Pressable>

        {/* Brand message */}
        <View style={styles.brandBanner}>
          <View style={styles.brandBannerText}>
            <Text style={styles.brandTag}>CARE • COMFORT • CONFIDENCE</Text>
            <Text style={styles.brandTitle}>
              Shopping that{'\n'}cares for you.
            </Text>
            <Text style={styles.brandDescription}>
              Your everyday essentials, all in one place.
            </Text>
          </View>
          <Text style={styles.brandBannerEmoji}>💗</Text>
        </View>

        {/* Categories */}
        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionTitle}>Shop by Category</Text>
            <Text style={styles.sectionSubtitle}>
              Find exactly what you need
            </Text>
          </View>
          <Text style={styles.sectionSymbol}>✦</Text>
        </View>

        <View style={styles.categoryGrid}>
          {categories.map((item, index) => (
            <Pressable
              key={item.title}
              onPress={goToHome}
              style={({ pressed }) => [
                styles.categoryCard,
                { backgroundColor: item.color },
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.categoryEmoji}>{item.emoji}</Text>
              <Text style={styles.categoryTitle}>{item.title}</Text>
              <Text style={styles.categorySubtitle}>{item.subtitle}</Text>
            </Pressable>
          ))}
        </View>

        {/* Collections */}
        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionTitle}>Discover More</Text>
            <Text style={styles.sectionSubtitle}>
              Explore our shopping collections
            </Text>
          </View>
        </View>

        {collections.map((item) => (
          <Pressable
            key={item.title}
            onPress={goToHome}
            style={({ pressed }) => [
              styles.collectionCard,
              { backgroundColor: item.color },
              pressed && styles.pressed,
            ]}
          >
            <View style={styles.collectionIcon}>
              <Text style={styles.collectionEmoji}>{item.emoji}</Text>
            </View>

            <View style={styles.collectionInfo}>
              <Text style={styles.collectionTitle}>{item.title}</Text>
              <Text style={styles.collectionDescription}>
                {item.description}
              </Text>
            </View>

            <Text style={styles.collectionArrow}>›</Text>
          </Pressable>
        ))}

        {/* Coming Soon */}
        <View style={styles.comingSoon}>
          <Text style={styles.comingEmoji}>🥑</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.comingTitle}>Groceries are coming!</Text>
            <Text style={styles.comingDescription}>
              Fresh everyday essentials, coming soon to Tipsy Cart.
            </Text>
          </View>
          <View style={styles.soonBadge}>
            <Text style={styles.soonText}>SOON</Text>
          </View>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerBrand}>TIPSY CART 💗</Text>
          <Text style={styles.footerText}>
            Care • Comfort • Confidence
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollContent: {
    paddingHorizontal: 20,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 22,
  },
  brand: {
    color: COLORS.primary,
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 2,
    marginBottom: 5,
  },
  heading: {
    fontSize: 30,
    fontWeight: '900',
    color: COLORS.dark,
  },
  subheading: {
    color: COLORS.muted,
    fontSize: 13,
    marginTop: 5,
  },
  headerIcon: {
    width: 52,
    height: 52,
    borderRadius: 18,
    backgroundColor: COLORS.lightPink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerEmoji: {
    fontSize: 25,
  },
  searchBanner: {
    backgroundColor: COLORS.white,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 15,
    paddingHorizontal: 15,
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  searchIcon: {
    fontSize: 17,
    marginRight: 10,
  },
  searchText: {
    flex: 1,
    color: COLORS.muted,
    fontSize: 13,
  },
  searchArrow: {
    color: COLORS.primary,
    fontSize: 26,
  },
  brandBanner: {
    backgroundColor: '#D63384',
    borderRadius: 22,
    padding: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 28,
    overflow: 'hidden',
  },
  brandBannerText: {
    flex: 1,
  },
  brandTag: {
    color: '#FFE0EF',
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1.1,
  },
  brandTitle: {
    color: COLORS.white,
    fontSize: 25,
    lineHeight: 31,
    fontWeight: '900',
    marginTop: 12,
  },
  brandDescription: {
    color: '#FFEAF3',
    fontSize: 11,
    marginTop: 9,
  },
  brandBannerEmoji: {
    fontSize: 55,
    marginLeft: 5,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: 19,
    fontWeight: '900',
    color: COLORS.dark,
  },
  sectionSubtitle: {
    color: COLORS.muted,
    fontSize: 12,
    marginTop: 4,
  },
  sectionSymbol: {
    color: COLORS.primary,
    fontSize: 23,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: 27,
  },
  categoryCard: {
    width: '48%',
    minHeight: 130,
    borderRadius: 18,
    padding: 14,
    marginBottom: 12,
    justifyContent: 'center',
  },
  categoryEmoji: {
    fontSize: 29,
    marginBottom: 10,
  },
  categoryTitle: {
    fontSize: 13,
    fontWeight: '900',
    color: COLORS.dark,
  },
  categorySubtitle: {
    fontSize: 11,
    color: COLORS.muted,
    marginTop: 5,
  },
  collectionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 15,
    borderRadius: 17,
    marginBottom: 11,
  },
  collectionIcon: {
    width: 45,
    height: 45,
    borderRadius: 14,
    backgroundColor: '#FFFFFFAA',
    alignItems: 'center',
    justifyContent: 'center',
  },
  collectionEmoji: {
    fontSize: 23,
  },
  collectionInfo: {
    flex: 1,
    marginLeft: 13,
  },
  collectionTitle: {
    fontSize: 14,
    fontWeight: '900',
    color: COLORS.dark,
  },
  collectionDescription: {
    fontSize: 11,
    color: COLORS.muted,
    marginTop: 5,
  },
  collectionArrow: {
    fontSize: 27,
    color: COLORS.primary,
  },
  comingSoon: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.white,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 15,
    marginTop: 13,
  },
  comingEmoji: {
    fontSize: 33,
    marginRight: 12,
  },
  comingTitle: {
    color: COLORS.dark,
    fontSize: 13,
    fontWeight: '900',
  },
  comingDescription: {
    color: COLORS.muted,
    fontSize: 10,
    marginTop: 5,
    lineHeight: 15,
  },
  soonBadge: {
    backgroundColor: COLORS.lightPink,
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: 8,
    marginLeft: 5,
  },
  soonText: {
    color: COLORS.primary,
    fontSize: 9,
    fontWeight: '900',
  },
  footer: {
    alignItems: 'center',
    paddingTop: 28,
    paddingBottom: 10,
  },
  footerBrand: {
    color: COLORS.primary,
    fontWeight: '900',
    fontSize: 13,
    letterSpacing: 2,
  },
  footerText: {
    color: COLORS.muted,
    fontSize: 11,
    marginTop: 7,
  },
  pressed: {
    opacity: 0.75,
  },
});
