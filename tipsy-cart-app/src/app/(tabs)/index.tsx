
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useRouter } from "expo-router";

const API_URL = "https://tipsy-cart.onrender.com/orders/products/";

const GUEST_CHECKOUT_API_URL =
  "https://tipsy-cart.onrender.com/orders/checkout/guest-order/";

const MOBILE_CHECKOUT_API_URL =
  "https://tipsy-cart.onrender.com/orders/checkout/mobile-order/";

const AUTH_TOKEN_STORAGE_KEY = "@tipsy_cart_auth_token_v1";
const CART_STORAGE_KEY = "@tipsy_cart_saved_cart_v1";
const SAVED_ADDRESSES_STORAGE_KEY = "@tipsy_cart_saved_addresses_v1";

type ShoppingSection = "everyday" | "groceries";

type Product = {
  id: number;
  name: string;
  description: string;
  category: string;
  subcategory: string;
  brand: string;
  image_url: string;
  price: number;
  stock: number;
};

type CartItem = Product & {
  quantity: number;
};

type PaymentMethod = "COD" | "UPI";

type CheckoutForm = {
  full_name: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
};

type SavedAddress = {
  id: string;
  full_name: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  isDefault: boolean;
};

const EVERYDAY_CATEGORIES = [
  "All",
  "Safety",
  "Personal Care",
  "Daily Essentials",
];

const GROCERY_CATEGORIES = [
  "All",
  "Fruits & Vegetables",
  "Atta, Rice & Pulses",
  "Dairy & Bakery",
  "Snacks & Beverages",
  "Household Essentials",
];

const EMPTY_FORM: CheckoutForm = {
  full_name: "",
  phone: "",
  address: "",
  city: "Kanpur",
  state: "Uttar Pradesh",
  pincode: "",
};

function formatPrice(price: number) {
  return `₹${Number(price || 0).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;
}

function normalizeProduct(item: any): Product | null {
  const id = Number(item?.id);
  const price = Number(item?.price);
  const stock = Number(item?.stock ?? 0);

  if (
    !Number.isInteger(id) ||
    id <= 0 ||
    typeof item?.name !== "string" ||
    !Number.isFinite(price) ||
    price < 0
  ) {
    return null;
  }

  return {
    id,
    name: item.name,
    description: String(item.description ?? ""),
    category: String(item.category ?? "Daily Essentials"),
    subcategory: String(item.subcategory ?? ""),
    brand: String(item.brand ?? ""),
    image_url: String(item.image_url ?? ""),
    price,
    stock: Math.max(0, Number.isFinite(stock) ? stock : 0),
  };
}

function normalizeSavedAddress(item: any): SavedAddress | null {
  if (!item || typeof item !== "object") {
    return null;
  }

  if (
    !item.id ||
    typeof item.full_name !== "string" ||
    typeof item.phone !== "string" ||
    typeof item.address !== "string" ||
    typeof item.city !== "string" ||
    typeof item.state !== "string" ||
    typeof item.pincode !== "string"
  ) {
    return null;
  }

  return {
    id: String(item.id),
    full_name: item.full_name,
    phone: item.phone,
    address: item.address,
    city: item.city,
    state: item.state,
    pincode: item.pincode,
    isDefault: item.isDefault === true,
  };
}

function getGroceryEmoji(subcategory: string) {
  const value = subcategory.toLowerCase();

  if (value.includes("fruit") || value.includes("vegetable")) {
    return "🥦";
  }

  if (
    value.includes("atta") ||
    value.includes("rice") ||
    value.includes("pulse")
  ) {
    return "🌾";
  }

  if (value.includes("dairy") || value.includes("bakery")) {
    return "🥛";
  }

  if (value.includes("snack") || value.includes("beverage")) {
    return "🥤";
  }

  if (value.includes("household")) {
    return "🧹";
  }

  return "🛒";
}

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);

  const [cartLoaded, setCartLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [shoppingSection, setShoppingSection] =
    useState<ShoppingSection>("everyday");

  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");

  const [cartVisible, setCartVisible] = useState(false);
  const [checkoutVisible, setCheckoutVisible] = useState(false);

  const [form, setForm] = useState<CheckoutForm>(EMPTY_FORM);
  const [paymentMethod, setPaymentMethod] =
    useState<PaymentMethod>("COD");
  const [submitting, setSubmitting] = useState(false);

  const [savedAddresses, setSavedAddresses] = useState<SavedAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(
    null
  );
  const [addressesLoading, setAddressesLoading] = useState(false);

  // Restore saved cart and load products.
  useEffect(() => {
    let active = true;

    async function initializeApp() {
      const productPromise = loadProducts(() => active);

      try {
        const savedCart = await AsyncStorage.getItem(CART_STORAGE_KEY);

        if (savedCart && active) {
          const parsed: unknown = JSON.parse(savedCart);

          if (Array.isArray(parsed)) {
            const restoredCart: CartItem[] = parsed
              .filter((item: any) => {
                return (
                  item &&
                  Number.isInteger(Number(item.id)) &&
                  Number(item.id) > 0 &&
                  typeof item.name === "string" &&
                  Number.isFinite(Number(item.price)) &&
                  Number(item.price) >= 0 &&
                  Number.isInteger(Number(item.quantity)) &&
                  Number(item.quantity) > 0
                );
              })
              .map((item: any) => ({
                id: Number(item.id),
                name: item.name,
                description: String(item.description ?? ""),
                category: String(item.category ?? "Daily Essentials"),
                subcategory: String(item.subcategory ?? ""),
                brand: String(item.brand ?? ""),
                image_url: String(item.image_url ?? ""),
                price: Number(item.price),
                stock: Math.max(0, Number(item.stock) || 0),
                quantity: Number(item.quantity),
              }));

            if (active) {
              setCart(restoredCart);
            }
          }
        }
      } catch (error) {
        console.warn("Could not restore saved cart:", error);
      } finally {
        if (active) {
          setCartLoaded(true);
        }
      }

      await productPromise;
    }

    void initializeApp();

    return () => {
      active = false;
    };
  }, []);

  async function loadProducts(isActive: () => boolean = () => true) {
    try {
      setLoading(true);
      setLoadError("");

      const response = await fetch(API_URL);

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      const rawProducts = Array.isArray(data)
        ? data
        : data?.products;

      if (!Array.isArray(rawProducts)) {
        throw new Error("Unexpected product response from server.");
      }

      const normalized = rawProducts
        .map(normalizeProduct)
        .filter((item: Product | null): item is Product => item !== null);

      if (isActive()) {
        setProducts(normalized);
      }
    } catch (error) {
      console.warn("Tipsy Cart product API error:", error);

      if (isActive()) {
        setLoadError(
          "Products load nahi ho rahe. Internet check karke retry karo."
        );
      }
    } finally {
      if (isActive()) {
        setLoading(false);
      }
    }
  }

  // Save cart after restoration is complete.
  useEffect(() => {
    if (!cartLoaded) {
      return;
    }

    AsyncStorage.setItem(
      CART_STORAGE_KEY,
      JSON.stringify(cart)
    ).catch((error) => {
      console.warn("Could not save cart:", error);
    });
  }, [cart, cartLoaded]);

  const categoryOptions =
    shoppingSection === "groceries"
      ? GROCERY_CATEGORIES
      : EVERYDAY_CATEGORIES;

  const sectionProducts = useMemo(() => {
    return products.filter((product) => {
      const isGrocery =
        product.category.trim().toLowerCase() === "groceries";

      return shoppingSection === "groceries"
        ? isGrocery
        : !isGrocery;
    });
  }, [products, shoppingSection]);

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return sectionProducts.filter((product) => {
      const matchesSearch =
        !query ||
        product.name.toLowerCase().includes(query) ||
        product.description.toLowerCase().includes(query) ||
        product.category.toLowerCase().includes(query) ||
        product.subcategory.toLowerCase().includes(query) ||
        product.brand.toLowerCase().includes(query);

      const matchesCategory =
        selectedCategory === "All" ||
        (shoppingSection === "groceries"
          ? product.subcategory.trim().toLowerCase() ===
            selectedCategory.toLowerCase()
          : product.category.trim().toLowerCase() ===
            selectedCategory.toLowerCase());

      return matchesSearch && matchesCategory;
    });
  }, [
    sectionProducts,
    search,
    selectedCategory,
    shoppingSection,
  ]);

  const cartCount = useMemo(
    () => cart.reduce((sum, item) => sum + item.quantity, 0),
    [cart]
  );

  const subtotal = useMemo(
    () =>
      cart.reduce(
        (sum, item) => sum + item.price * item.quantity,
        0
      ),
    [cart]
  );

  function switchShoppingSection(section: ShoppingSection) {
    setShoppingSection(section);
    setSelectedCategory("All");
    setSearch("");
  }

  function addToCart(product: Product) {
    if (!cartLoaded) {
      Alert.alert("Please wait", "Cart abhi load ho raha hai.");
      return;
    }

    if (product.stock <= 0) {
      Alert.alert("Out of stock", "Yeh product abhi available nahi hai.");
      return;
    }

    const existing = cart.find((item) => item.id === product.id);

    if (existing && existing.quantity >= product.stock) {
      Alert.alert(
        "Stock limit",
        `Is product ke sirf ${product.stock} pieces available hain.`
      );
      return;
    }

    setCart((current) => {
      const found = current.find((item) => item.id === product.id);

      if (found) {
        return current.map((item) =>
          item.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }

      return [...current, { ...product, quantity: 1 }];
    });
  }

  function changeQuantity(productId: number, change: number) {
    setCart((current) =>
      current
        .map((item) => {
          if (item.id !== productId) {
            return item;
          }

          const nextQuantity = item.quantity + change;

          if (nextQuantity <= 0) {
            return item;
          }

          if (nextQuantity > item.stock) {
            Alert.alert(
              "Stock limit",
              `Sirf ${item.stock} pieces available hain.`
            );
            return item;
          }

          return { ...item, quantity: nextQuantity };
        })
        .filter((item) => item.quantity > 0)
    );
  }

  function removeFromCart(productId: number) {
    setCart((current) =>
      current.filter((item) => item.id !== productId)
    );
  }

  function clearCart() {
    Alert.alert(
      "Clear cart?",
      "Saare products cart se remove ho jayenge.",
      [
        { text: "Keep items", style: "cancel" },
        {
          text: "Clear cart",
          style: "destructive",
          onPress: () => setCart([]),
        },
      ]
    );
  }

  function updateForm(field: keyof CheckoutForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setSelectedAddressId(null);
  }

  function applySavedAddress(address: SavedAddress) {
    setSelectedAddressId(address.id);

    setForm({
      full_name: address.full_name,
      phone: address.phone.replace(/\D/g, "").slice(0, 10),
      address: address.address,
      city: address.city,
      state: address.state,
      pincode: address.pincode,
    });
  }

  async function loadSavedAddresses() {
    try {
      setAddressesLoading(true);

      const stored = await AsyncStorage.getItem(
        SAVED_ADDRESSES_STORAGE_KEY
      );

      if (!stored) {
        setSavedAddresses([]);
        setSelectedAddressId(null);
        return;
      }

      const parsed: unknown = JSON.parse(stored);

      if (!Array.isArray(parsed)) {
        setSavedAddresses([]);
        setSelectedAddressId(null);
        return;
      }

      const addresses = parsed
        .map(normalizeSavedAddress)
        .filter(
          (item: SavedAddress | null): item is SavedAddress =>
            item !== null
        );

      setSavedAddresses(addresses);

      const defaultAddress =
        addresses.find((item) => item.isDefault) ?? addresses[0];

      if (defaultAddress) {
        applySavedAddress(defaultAddress);
      } else {
        setSelectedAddressId(null);
      }
    } catch (error) {
      console.warn("Could not load saved addresses:", error);
      Alert.alert(
        "Address issue",
        "Saved addresses load nahi ho paaye. Aap manually address enter kar sakte hain."
      );
    } finally {
      setAddressesLoading(false);
    }
  }

  async function openCheckout() {
    if (!cartLoaded || cart.length === 0) {
      Alert.alert("Empty cart", "Checkout se pehle products add karo.");
      return;
    }

    setCartVisible(false);
    setCheckoutVisible(true);

    await loadSavedAddresses();
  }

  function openAddressManager() {
    if (submitting) {
      return;
    }

    setCheckoutVisible(false);
    router.push("/addresses");
  }

  function validateCheckout(): boolean {
    const name = form.full_name.trim();
    const phone = form.phone.replace(/\D/g, "");
    const address = form.address.trim();
    const city = form.city.trim();
    const state = form.state.trim();
    const pincode = form.pincode.trim();

    if (!name || !address || !city || !state || !phone || !pincode) {
      Alert.alert("Missing details", "Saari delivery details fill karo.");
      return false;
    }

    if (name.length > 150) {
      Alert.alert("Invalid name", "Name 150 characters se chhota hona chahiye.");
      return false;
    }

    if (!/^[6-9]\d{9}$/.test(phone)) {
      Alert.alert(
        "Invalid phone",
        "Valid 10-digit Indian mobile number enter karo."
      );
      return false;
    }

    if (!/^\d{6}$/.test(pincode)) {
      Alert.alert("Invalid pincode", "6-digit pincode enter karo.");
      return false;
    }

    if (address.length > 255) {
      Alert.alert("Address too long", "Address 255 characters se chhota rakho.");
      return false;
    }

    return true;
  }

  // Both shopping sections use the same checkout APIs.
  async function handleContinueCheckout() {
    if (submitting) {
      return;
    }

    if (!validateCheckout()) {
      return;
    }

    if (!cartLoaded || cart.length === 0) {
      Alert.alert("Empty cart", "Checkout se pehle products add karo.");
      return;
    }

    const orderItems = cart.map((item) => ({
      product_id: item.id,
      quantity: item.quantity,
    }));

    setSubmitting(true);

    try {
      const payload = {
        full_name: form.full_name.trim(),
        phone: form.phone.replace(/\D/g, ""),
        address: form.address.trim(),
        city: form.city.trim(),
        state: form.state.trim(),
        pincode: form.pincode.trim(),
        payment_method: paymentMethod,
        items: orderItems,
      };

      const token = await AsyncStorage.getItem(
        AUTH_TOKEN_STORAGE_KEY
      );

      const checkoutUrl = token
        ? MOBILE_CHECKOUT_API_URL
        : GUEST_CHECKOUT_API_URL;

      const headers: Record<string, string> = {
        Accept: "application/json",
        "Content-Type": "application/json",
      };

      if (token) {
        headers.Authorization = `Token ${token}`;
      }

      const response = await fetch(checkoutUrl, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const responseText = await response.text();

      let result: any = null;

      try {
        result = responseText ? JSON.parse(responseText) : null;
      } catch {
        throw new Error(
          "Server ka response samajh nahi aaya. Order status verify karke hi dobara try karo."
        );
      }

      if (token && response.status === 401) {
        Alert.alert(
          "Login expired",
          "Aapka login session expire ho gaya hai. Please dobara login karke order place karo. Aapka cart safe hai."
        );
        return;
      }

      if (!response.ok) {
        const message =
          typeof result?.error === "string"
            ? result.error
            : typeof result?.message === "string"
            ? result.message
            : `Order place nahi hua. Server error: ${response.status}`;

        throw new Error(message);
      }

      if (result?.success !== true || !result?.order_id) {
        throw new Error(
          "Server se order confirmation nahi mila. Dobara try karne se pehle order status verify karo."
        );
      }

      const orderId = result.order_id;
      const serverTotal = result.total_amount ?? result.total;

      setCart([]);

      try {
        await AsyncStorage.setItem(
          CART_STORAGE_KEY,
          JSON.stringify([])
        );
      } catch (storageError) {
        console.warn("Could not clear saved cart:", storageError);
      }

      setCheckoutVisible(false);
      setForm(EMPTY_FORM);
      setSelectedAddressId(null);
      setPaymentMethod("COD");

      Alert.alert(
        "Order received!",
        `Order number: #${orderId}\nTotal: ${formatPrice(
          Number(serverTotal ?? 0)
        )}\nStatus: ${result.status ?? "Pending"}\nPayment: ${
          paymentMethod === "COD"
            ? "Cash on Delivery"
            : "UPI payment is not completed"
        }\n\n${
          result.message ?? "Your order has been received."
        }`,
        [{ text: "OK" }]
      );
    } catch (error) {
      console.warn("Tipsy Cart checkout error:", error);

      const message =
        error instanceof Error
          ? error.message
          : "Order place nahi ho saka. Please try again.";

      Alert.alert("Checkout issue", message);
    } finally {
      setSubmitting(false);
    }
  }

  function renderProduct({ item }: { item: Product }) {
    const cartItem = cart.find(
      (cartProduct) => cartProduct.id === item.id
    );

    const isGrocery =
      item.category.trim().toLowerCase() === "groceries";

    const categoryLabel = isGrocery
      ? item.subcategory || "Groceries"
      : item.category;

    const fallbackEmoji = isGrocery
      ? getGroceryEmoji(item.subcategory)
      : item.category.toLowerCase().includes("safety")
      ? "🛡️"
      : item.category.toLowerCase().includes("personal")
      ? "🧴"
      : "🛍️";

    return (
      <View style={styles.productCard}>
        <View
          style={[
            styles.productIcon,
            isGrocery && styles.groceryProductIcon,
          ]}
        >
          {item.image_url ? (
            <Image
              source={{ uri: item.image_url }}
              style={styles.productImage}
              resizeMode="contain"
            />
          ) : (
            <Text style={styles.productEmoji}>{fallbackEmoji}</Text>
          )}
        </View>

        <Text style={styles.productCategory}>{categoryLabel}</Text>

        {!!item.brand && (
          <Text style={styles.productBrand} numberOfLines={1}>
            {item.brand}
          </Text>
        )}

        <Text style={styles.productName} numberOfLines={2}>
          {item.name}
        </Text>

        <Text style={styles.productDescription} numberOfLines={2}>
          {item.description || "Quality essentials for everyday life."}
        </Text>

        <Text style={styles.productPrice}>
          {formatPrice(item.price)}
        </Text>

        <Text style={styles.stockText}>
          {item.stock > 0 ? `${item.stock} available` : "Out of stock"}
        </Text>

        <Pressable
          style={[
            styles.addButton,
            (item.stock <= 0 || !cartLoaded) && styles.disabledButton,
          ]}
          disabled={item.stock <= 0 || !cartLoaded}
          onPress={() => addToCart(item)}
        >
          <Text style={styles.addButtonText}>
            {cartItem ? `Add more (${cartItem.quantity})` : "+ Add to Cart"}
          </Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View
      style={[
        styles.safeArea,
        {
          paddingTop: insets.top + 8,
          paddingBottom: insets.bottom,
        },
      ]}
    >
      <StatusBar barStyle="dark-content" />

      <View style={styles.header}>
        <View>
          <Text style={styles.brandName}>Tipsy Cart</Text>
          <Text style={styles.brandTagline}>
            Care • Comfort • Confidence
          </Text>
        </View>

        <Pressable
          style={styles.cartButton}
          onPress={() => setCartVisible(true)}
        >
          <Text style={styles.cartButtonText}>
            🛒 Cart ({cartCount})
          </Text>
        </Pressable>
      </View>

      <FlatList
        data={filteredProducts}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderProduct}
        numColumns={2}
        columnWrapperStyle={styles.productRow}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <View>
            {/* Main shopping section selector */}
            <View style={styles.sectionSwitch}>
              <Pressable
                style={[
                  styles.sectionSwitchCard,
                  shoppingSection === "everyday" &&
                    styles.sectionSwitchCardActive,
                ]}
                onPress={() => switchShoppingSection("everyday")}
              >
                <Text style={styles.sectionSwitchEmoji}>💗</Text>
                <View style={styles.sectionSwitchTextContainer}>
                  <Text
                    style={[
                      styles.sectionSwitchTitle,
                      shoppingSection === "everyday" &&
                        styles.sectionSwitchTitleActive,
                    ]}
                  >
                    Tipsy Cart
                  </Text>
                  <Text
                    style={[
                      styles.sectionSwitchSubtitle,
                      shoppingSection === "everyday" &&
                        styles.sectionSwitchSubtitleActive,
                    ]}
                  >
                    Care & essentials
                  </Text>
                </View>
              </Pressable>

              <Pressable
                style={[
                  styles.sectionSwitchCard,
                  shoppingSection === "groceries" &&
                    styles.grocerySwitchCardActive,
                ]}
                onPress={() => switchShoppingSection("groceries")}
              >
                <Text style={styles.sectionSwitchEmoji}>🥬</Text>
                <View style={styles.sectionSwitchTextContainer}>
                  <Text
                    style={[
                      styles.sectionSwitchTitle,
                      shoppingSection === "groceries" &&
                        styles.grocerySwitchTitleActive,
                    ]}
                  >
                    Groceries
                  </Text>
                  <Text
                    style={[
                      styles.sectionSwitchSubtitle,
                      shoppingSection === "groceries" &&
                        styles.grocerySwitchSubtitleActive,
                    ]}
                  >
                    Fresh daily needs
                  </Text>
                </View>
              </Pressable>
            </View>

            <View
              style={[
                styles.hero,
                shoppingSection === "groceries" && styles.groceryHero,
              ]}
            >
              <Text
                style={[
                  styles.heroEyebrow,
                  shoppingSection === "groceries" &&
                    styles.groceryHeroEyebrow,
                ]}
              >
                {shoppingSection === "groceries"
                  ? "YOUR DAILY GROCERY STORE"
                  : "YOUR EVERYDAY CARE STORE"}
              </Text>

              <Text
                style={[
                  styles.heroTitle,
                  shoppingSection === "groceries" &&
                    styles.groceryHeroTitle,
                ]}
              >
                {shoppingSection === "groceries"
                  ? "Fresh choices.\nEveryday comfort."
                  : "Your needs.\nYour comfort."}
              </Text>

              <Text
                style={[
                  styles.heroDescription,
                  shoppingSection === "groceries" &&
                    styles.groceryHeroDescription,
                ]}
              >
                {shoppingSection === "groceries"
                  ? "Fruits, vegetables, daily staples and household essentials in one place."
                  : "Personal care, daily essentials and safety products delivered with care."}
              </Text>
            </View>

            <View style={styles.trustRow}>
              <Text style={styles.trustText}>
                {shoppingSection === "groceries"
                  ? "🥬 Daily essentials"
                  : "♡ Everyday care"}
              </Text>
              <Text style={styles.trustText}>✓ Easy shopping</Text>
            </View>

            <TextInput
              style={styles.searchInput}
              placeholder={
                shoppingSection === "groceries"
                  ? "Search groceries..."
                  : "Search products..."
              }
              placeholderTextColor="#A18B96"
              value={search}
              onChangeText={setSearch}
              autoCorrect={false}
              returnKeyType="search"
            />

            <Text style={styles.sectionTitle}>
              {shoppingSection === "groceries"
                ? "Shop grocery categories"
                : "Shop by category"}
            </Text>

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.categoryRow}
            >
              {categoryOptions.map((category) => (
                <Pressable
                  key={category}
                  onPress={() => setSelectedCategory(category)}
                  style={[
                    styles.categoryChip,
                    selectedCategory === category &&
                      styles.categoryChipActive,
                    shoppingSection === "groceries" &&
                      selectedCategory === category &&
                      styles.groceryCategoryChipActive,
                  ]}
                >
                  <Text
                    style={[
                      styles.categoryText,
                      selectedCategory === category &&
                        styles.categoryTextActive,
                    ]}
                  >
                    {category}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>

            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>
                {shoppingSection === "groceries"
                  ? "Fresh groceries"
                  : "Our products"}
              </Text>
              <Text style={styles.productCount}>
                {filteredProducts.length} items
              </Text>
            </View>

            {loading && (
              <View style={styles.statusContainer}>
                <ActivityIndicator
                  size="large"
                  color={
                    shoppingSection === "groceries" ? "#39834C" : "#D63384"
                  }
                />
                <Text style={styles.statusText}>
                  Loading products...
                </Text>
              </View>
            )}

            {!loading && !!loadError && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{loadError}</Text>
                <Pressable
                  style={styles.retryButton}
                  onPress={() => void loadProducts()}
                >
                  <Text style={styles.retryButtonText}>Retry</Text>
                </Pressable>
              </View>
            )}

            {!loading && !loadError && products.length === 0 && (
              <Text style={styles.emptyMessage}>
                Abhi koi product available nahi hai.
              </Text>
            )}

            {!loading &&
              !loadError &&
              products.length > 0 &&
              sectionProducts.length === 0 && (
                <Text style={styles.emptyMessage}>
                  {shoppingSection === "groceries"
                    ? "Groceries section mein products jald add honge. Stay tuned!"
                    : "Abhi is section mein koi product available nahi hai."}
                </Text>
              )}
          </View>
        }
        ListEmptyComponent={
          !loading &&
          !loadError &&
          sectionProducts.length > 0 ? (
            <Text style={styles.emptyMessage}>
              Is search ya category mein product nahi mila.
            </Text>
          ) : undefined
        }
        ListFooterComponent={
          <View style={styles.footer}>
            <Text style={styles.footerTitle}>Tipsy Cart</Text>
            <Text style={styles.footerText}>
              Thoughtful essentials for everyday life.
            </Text>
            <Text style={styles.footerSmall}>
              Your comfort and privacy matter to us.
            </Text>
          </View>
        }
      />

      {/* Shopping cart modal */}
      <Modal
        visible={cartVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setCartVisible(false)}
      >
        <SafeAreaView style={styles.modalSafeArea}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Your Cart</Text>
            <Pressable onPress={() => setCartVisible(false)}>
              <Text style={styles.closeButton}>✕</Text>
            </Pressable>
          </View>

          {!cartLoaded ? (
            <ActivityIndicator
              size="large"
              color="#D63384"
              style={styles.modalLoader}
            />
          ) : cart.length === 0 ? (
            <View style={styles.emptyCart}>
              <Text style={styles.emptyCartEmoji}>🛒</Text>
              <Text style={styles.emptyCartTitle}>
                Your cart is empty
              </Text>
              <Text style={styles.emptyCartText}>
                Products add karo aur shopping continue karo.
              </Text>
              <Pressable
                style={styles.primaryButton}
                onPress={() => setCartVisible(false)}
              >
                <Text style={styles.primaryButtonText}>
                  Continue Shopping
                </Text>
              </Pressable>
            </View>
          ) : (
            <>
              <FlatList
                data={cart}
                keyExtractor={(item) => String(item.id)}
                contentContainerStyle={styles.cartList}
                renderItem={({ item }) => (
                  <View style={styles.cartItem}>
                    <View style={styles.cartItemInfo}>
                      <Text style={styles.cartItemName}>
                        {item.name}
                      </Text>
                      <Text style={styles.cartItemPrice}>
                        {formatPrice(item.price)} each
                      </Text>
                      <Text style={styles.cartItemSubtotal}>
                        Total: {formatPrice(item.price * item.quantity)}
                      </Text>
                    </View>

                    <View style={styles.quantityControls}>
                      <Pressable
                        style={styles.quantityButton}
                        onPress={() => changeQuantity(item.id, -1)}
                      >
                        <Text style={styles.quantityButtonText}>−</Text>
                      </Pressable>

                      <Text style={styles.quantityValue}>
                        {item.quantity}
                      </Text>

                      <Pressable
                        style={styles.quantityButton}
                        onPress={() => changeQuantity(item.id, 1)}
                      >
                        <Text style={styles.quantityButtonText}>+</Text>
                      </Pressable>
                    </View>

                    <Pressable
                      onPress={() => removeFromCart(item.id)}
                    >
                      <Text style={styles.removeText}>Remove</Text>
                    </Pressable>
                  </View>
                )}
              />

              <View style={styles.cartSummary}>
                <View style={styles.summaryRow}>
                  <Text style={styles.summaryLabel}>Items</Text>
                  <Text style={styles.summaryValue}>
                    {cartCount}
                  </Text>
                </View>

                <View style={styles.summaryRow}>
                  <Text style={styles.summaryLabel}>Subtotal</Text>
                  <Text style={styles.summaryTotal}>
                    {formatPrice(subtotal)}
                  </Text>
                </View>

                <Text style={styles.summaryNote}>
                  Delivery charges, if applicable, will be confirmed at checkout.
                </Text>

                <Pressable
                  style={styles.primaryButton}
                  onPress={() => void openCheckout()}
                >
                  <Text style={styles.primaryButtonText}>
                    Proceed to Checkout
                  </Text>
                </Pressable>

                <Pressable
                  style={styles.clearButton}
                  onPress={clearCart}
                >
                  <Text style={styles.clearButtonText}>
                    Clear Cart
                  </Text>
                </Pressable>
              </View>
            </>
          )}
        </SafeAreaView>
      </Modal>

      {/* Checkout form */}
      <Modal
        visible={checkoutVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setCheckoutVisible(false)}
      >
        <SafeAreaView style={styles.modalSafeArea}>
          <KeyboardAvoidingView
            style={styles.flex}
            behavior={Platform.OS === "ios" ? "padding" : undefined}
          >
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                Delivery Details
              </Text>
              <Pressable
                onPress={() => {
                  if (!submitting) {
                    setCheckoutVisible(false);
                  }
                }}
              >
                <Text style={styles.closeButton}>✕</Text>
              </Pressable>
            </View>

            <ScrollView
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={styles.checkoutContent}
            >
              <Text style={styles.checkoutIntro}>
                Enter your details to continue with your order.
              </Text>

              {/* Saved addresses */}
              <View style={styles.savedAddressHeader}>
                <Text style={styles.savedAddressHeading}>
                  📍 Saved Addresses
                </Text>

                <Pressable onPress={openAddressManager}>
                  <Text style={styles.manageAddressText}>
                    + Add / Manage
                  </Text>
                </Pressable>
              </View>

              {addressesLoading ? (
                <View style={styles.addressLoading}>
                  <ActivityIndicator size="small" color="#D63384" />
                  <Text style={styles.addressLoadingText}>
                    Loading saved addresses...
                  </Text>
                </View>
              ) : savedAddresses.length > 0 ? (
                <View style={styles.savedAddressList}>
                  {savedAddresses.map((address) => {
                    const selected =
                      selectedAddressId === address.id;

                    return (
                      <Pressable
                        key={address.id}
                        style={[
                          styles.savedAddressCard,
                          selected && styles.savedAddressCardActive,
                        ]}
                        onPress={() => applySavedAddress(address)}
                      >
                        <View style={styles.savedAddressTop}>
                          <Text style={styles.savedAddressName}>
                            {address.full_name}
                          </Text>

                          <Text
                            style={[
                              styles.addressRadio,
                              selected && styles.addressRadioActive,
                            ]}
                          >
                            {selected ? "●" : "○"}
                          </Text>
                        </View>

                        {address.isDefault && (
                          <Text style={styles.defaultAddressBadge}>
                            DEFAULT ADDRESS
                          </Text>
                        )}

                        <Text style={styles.savedAddressDetails}>
                          {address.address}
                        </Text>
                        <Text style={styles.savedAddressDetails}>
                          {address.city}, {address.state} - {address.pincode}
                        </Text>
                        <Text style={styles.savedAddressPhone}>
                          📞 {address.phone}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              ) : (
                <View style={styles.noSavedAddress}>
                  <Text style={styles.noSavedAddressText}>
                    Abhi koi saved address nahi hai. Aap neeche manually
                    details enter kar sakte hain.
                  </Text>

                  <Pressable onPress={openAddressManager}>
                    <Text style={styles.addFirstAddressText}>
                      + Save a new address
                    </Text>
                  </Pressable>
                </View>
              )}

              <Text style={styles.fieldLabel}>Full name *</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.full_name}
                onChangeText={(value) =>
                  updateForm("full_name", value)
                }
                placeholder="Enter your full name"
                maxLength={150}
                autoCapitalize="words"
              />

              <Text style={styles.fieldLabel}>Mobile number *</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.phone}
                onChangeText={(value) =>
                  updateForm(
                    "phone",
                    value.replace(/\D/g, "").slice(0, 10)
                  )
                }
                placeholder="10-digit mobile number"
                keyboardType="phone-pad"
                maxLength={10}
              />

              <Text style={styles.fieldLabel}>
                Full delivery address *
              </Text>
              <TextInput
                style={[styles.fieldInput, styles.multilineInput]}
                value={form.address}
                onChangeText={(value) =>
                  updateForm("address", value)
                }
                placeholder="House number, street, area"
                multiline
                maxLength={255}
              />

              <Text style={styles.fieldLabel}>City *</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.city}
                onChangeText={(value) =>
                  updateForm("city", value)
                }
                placeholder="City"
                maxLength={100}
              />

              <Text style={styles.fieldLabel}>State *</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.state}
                onChangeText={(value) =>
                  updateForm("state", value)
                }
                placeholder="State"
                maxLength={100}
              />

              <Text style={styles.fieldLabel}>Pincode *</Text>
              <TextInput
                style={styles.fieldInput}
                value={form.pincode}
                onChangeText={(value) =>
                  updateForm(
                    "pincode",
                    value.replace(/\D/g, "").slice(0, 6)
                  )
                }
                placeholder="6-digit pincode"
                keyboardType="number-pad"
                maxLength={6}
              />

              <Text style={styles.fieldLabel}>Payment method</Text>

              <Pressable
                style={[
                  styles.paymentOption,
                  paymentMethod === "COD" &&
                    styles.paymentOptionActive,
                ]}
                onPress={() => setPaymentMethod("COD")}
              >
                <Text style={styles.paymentOptionText}>
                  {paymentMethod === "COD" ? "◉" : "○"}  Cash on Delivery
                </Text>
              </Pressable>

              <Pressable
                style={[
                  styles.paymentOption,
                  paymentMethod === "UPI" &&
                    styles.paymentOptionActive,
                ]}
                onPress={() => setPaymentMethod("UPI")}
              >
                <Text style={styles.paymentOptionText}>
                  {paymentMethod === "UPI" ? "◉" : "○"}  UPI
                </Text>
              </Pressable>

              <View style={styles.checkoutTotal}>
                <Text style={styles.summaryLabel}>
                  Order subtotal
                </Text>
                <Text style={styles.summaryTotal}>
                  {formatPrice(subtotal)}
                </Text>
              </View>

              <Pressable
                style={[
                  styles.primaryButton,
                  submitting && styles.disabledButton,
                ]}
                disabled={submitting}
                onPress={() => void handleContinueCheckout()}
              >
                <Text style={styles.primaryButtonText}>
                  {submitting ? "Please wait..." : "Place Order"}
                </Text>
              </Pressable>

              <Text style={styles.checkoutDisclaimer}>
                Order submit hone par server stock aur price verify karega.
                UPI payment gateway abhi connected nahi hai; UPI choose
                karne se payment complete nahi hogi.
              </Text>
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },

  safeArea: {
    flex: 1,
    backgroundColor: "#FFF8FA",
  },

  modalSafeArea: {
    flex: 1,
    backgroundColor: "#FFF8FA",
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: "#FFF8FA",
    borderBottomWidth: 1,
    borderBottomColor: "#F1DFE8",
  },

  brandName: {
    fontSize: 25,
    fontWeight: "900",
    color: "#C21868",
    letterSpacing: 0.2,
  },

  brandTagline: {
    fontSize: 11,
    color: "#806676",
    marginTop: 3,
  },

  cartButton: {
    backgroundColor: "#D63384",
    paddingVertical: 11,
    paddingHorizontal: 15,
    borderRadius: 15,
    elevation: 2,
  },

  cartButtonText: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: 13,
  },

  listContent: {
    paddingHorizontal: 20,
    paddingBottom: 35,
  },

  sectionSwitch: {
    flexDirection: "row",
    gap: 10,
    marginTop: 15,
    marginBottom: 2,
  },

  sectionSwitchCard: {
    flex: 1,
    minHeight: 76,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 11,
    paddingVertical: 12,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#EEDCE5",
    borderRadius: 17,
    gap: 8,
  },

  sectionSwitchCardActive: {
    backgroundColor: "#FCE4EF",
    borderColor: "#D63384",
    borderWidth: 1.5,
  },

  grocerySwitchCardActive: {
    backgroundColor: "#EAF6E9",
    borderColor: "#55965C",
    borderWidth: 1.5,
  },

  sectionSwitchEmoji: {
    fontSize: 25,
  },

  sectionSwitchTextContainer: {
    flex: 1,
  },

  sectionSwitchTitle: {
    color: "#513347",
    fontWeight: "900",
    fontSize: 13,
  },

  sectionSwitchTitleActive: {
    color: "#B71F68",
  },

  grocerySwitchTitleActive: {
    color: "#32733D",
  },

  sectionSwitchSubtitle: {
    color: "#967E8C",
    fontSize: 9,
    marginTop: 4,
  },

  sectionSwitchSubtitleActive: {
    color: "#9E3C6C",
  },

  grocerySwitchSubtitleActive: {
    color: "#4D8053",
  },

  hero: {
    marginTop: 14,
    padding: 23,
    borderRadius: 24,
    backgroundColor: "#FCE4EF",
    borderWidth: 1,
    borderColor: "#F7D4E4",
  },

  groceryHero: {
    backgroundColor: "#EAF6E9",
    borderColor: "#D2E9D0",
  },

  heroEyebrow: {
    color: "#B51D65",
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 1.3,
  },

  groceryHeroEyebrow: {
    color: "#367A42",
  },

  heroTitle: {
    fontSize: 31,
    fontWeight: "900",
    color: "#55163A",
    lineHeight: 37,
    marginTop: 10,
  },

  groceryHeroTitle: {
    color: "#245C2D",
  },

  heroDescription: {
    color: "#77536A",
    fontSize: 13,
    lineHeight: 20,
    marginTop: 11,
  },

  groceryHeroDescription: {
    color: "#55765A",
  },

  trustRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    paddingVertical: 17,
  },

  trustText: {
    color: "#8B3864",
    fontWeight: "700",
    fontSize: 12,
  },

  searchInput: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#EED6E2",
    borderRadius: 15,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: "#351B2A",
    fontSize: 14,
    marginBottom: 21,
  },

  sectionTitle: {
    fontSize: 18,
    fontWeight: "900",
    color: "#351B2A",
  },

  categoryRow: {
    paddingVertical: 14,
    gap: 9,
  },

  categoryChip: {
    borderWidth: 1,
    borderColor: "#E8CBD9",
    borderRadius: 22,
    paddingHorizontal: 17,
    paddingVertical: 10,
    backgroundColor: "#FFFFFF",
  },

  categoryChipActive: {
    backgroundColor: "#D63384",
    borderColor: "#D63384",
  },

  groceryCategoryChipActive: {
    backgroundColor: "#43894D",
    borderColor: "#43894D",
  },

  categoryText: {
    color: "#754B62",
    fontSize: 12,
    fontWeight: "700",
  },

  categoryTextActive: {
    color: "#FFFFFF",
  },

  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 10,
    marginBottom: 14,
  },

  productCount: {
    color: "#967B8C",
    fontSize: 12,
  },

  productRow: {
    justifyContent: "space-between",
    gap: 10,
  },

  productCard: {
    width: "48.5%",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#F0DFE8",
    elevation: 2,
  },

  productIcon: {
    height: 112,
    borderRadius: 15,
    backgroundColor: "#FFF0F6",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 11,
    overflow: "hidden",
  },

  groceryProductIcon: {
    backgroundColor: "#F0F8ED",
  },

  productImage: {
    width: "100%",
    height: "100%",
  },

  productEmoji: {
    fontSize: 45,
  },

  productCategory: {
    color: "#C02770",
    fontSize: 10,
    fontWeight: "800",
    textTransform: "uppercase",
  },

  productBrand: {
    color: "#8A7782",
    fontSize: 10,
    marginTop: 4,
    fontWeight: "700",
  },

  productName: {
    color: "#351B2A",
    fontWeight: "800",
    fontSize: 14,
    marginTop: 6,
    minHeight: 36,
  },

  productDescription: {
    color: "#8A7782",
    fontSize: 11,
    lineHeight: 15,
    marginTop: 5,
    minHeight: 30,
  },

  productPrice: {
    color: "#B71F68",
    fontSize: 17,
    fontWeight: "900",
    marginTop: 9,
  },

  stockText: {
    color: "#8C7C85",
    fontSize: 10,
    marginTop: 4,
  },

  addButton: {
    backgroundColor: "#D63384",
    borderRadius: 12,
    paddingVertical: 11,
    paddingHorizontal: 5,
    alignItems: "center",
    marginTop: 11,
  },

  addButtonText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "800",
  },

  disabledButton: {
    opacity: 0.45,
  },

  statusContainer: {
    alignItems: "center",
    padding: 30,
  },

  statusText: {
    color: "#806676",
    marginTop: 10,
  },

  errorBox: {
    padding: 16,
    backgroundColor: "#FFF0F0",
    borderRadius: 15,
    marginVertical: 12,
  },

  errorText: {
    color: "#A51D32",
    lineHeight: 20,
  },

  retryButton: {
    backgroundColor: "#D63384",
    alignSelf: "flex-start",
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 11,
    marginTop: 11,
  },

  retryButtonText: {
    color: "#FFFFFF",
    fontWeight: "800",
  },

  emptyMessage: {
    color: "#806676",
    textAlign: "center",
    padding: 25,
    lineHeight: 21,
  },

  footer: {
    alignItems: "center",
    paddingVertical: 30,
    borderTopWidth: 1,
    borderTopColor: "#F1E1E9",
    marginTop: 14,
  },

  footerTitle: {
    fontSize: 18,
    fontWeight: "900",
    color: "#C21868",
  },

  footerText: {
    color: "#806676",
    marginTop: 6,
    fontSize: 12,
  },

  footerSmall: {
    color: "#A28D99",
    marginTop: 9,
    fontSize: 10,
  },

  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 17,
    borderBottomWidth: 1,
    borderBottomColor: "#F0E1E9",
  },

  modalTitle: {
    color: "#351B2A",
    fontSize: 23,
    fontWeight: "900",
  },

  closeButton: {
    color: "#8D5471",
    fontSize: 23,
    paddingHorizontal: 5,
  },

  modalLoader: {
    marginTop: 40,
  },

  emptyCart: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 25,
  },

  emptyCartEmoji: {
    fontSize: 55,
  },

  emptyCartTitle: {
    fontSize: 20,
    fontWeight: "900",
    color: "#351B2A",
    marginTop: 15,
  },

  emptyCartText: {
    color: "#806676",
    textAlign: "center",
    marginTop: 8,
    marginBottom: 20,
  },

  cartList: {
    paddingHorizontal: 20,
    paddingBottom: 10,
  },

  cartItem: {
    paddingVertical: 18,
    borderBottomWidth: 1,
    borderBottomColor: "#F1E5EB",
    gap: 10,
  },

  cartItemInfo: {
    flex: 1,
  },

  cartItemName: {
    fontSize: 15,
    color: "#351B2A",
    fontWeight: "800",
  },

  cartItemPrice: {
    color: "#8A7782",
    marginTop: 4,
    fontSize: 12,
  },

  cartItemSubtotal: {
    color: "#B71F68",
    fontWeight: "800",
    marginTop: 5,
  },

  quantityControls: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },

  quantityButton: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: "#FCE4EF",
    alignItems: "center",
    justifyContent: "center",
  },

  quantityButtonText: {
    fontSize: 20,
    color: "#B71F68",
    fontWeight: "900",
  },

  quantityValue: {
    color: "#351B2A",
    fontSize: 15,
    fontWeight: "800",
  },

  removeText: {
    color: "#C02D59",
    fontWeight: "700",
    fontSize: 12,
  },

  cartSummary: {
    paddingHorizontal: 20,
    paddingTop: 17,
    paddingBottom: 24,
    borderTopWidth: 1,
    borderTopColor: "#F0E1E9",
    backgroundColor: "#FFF8FA",
  },

  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 9,
  },

  summaryLabel: {
    color: "#806676",
    fontSize: 14,
  },

  summaryValue: {
    color: "#351B2A",
    fontWeight: "800",
  },

  summaryTotal: {
    color: "#B71F68",
    fontSize: 20,
    fontWeight: "900",
  },

  summaryNote: {
    color: "#998692",
    fontSize: 11,
    lineHeight: 16,
    marginBottom: 14,
  },

  primaryButton: {
    backgroundColor: "#D63384",
    paddingVertical: 15,
    paddingHorizontal: 18,
    alignItems: "center",
    borderRadius: 15,
    marginTop: 9,
  },

  primaryButtonText: {
    color: "#FFFFFF",
    fontWeight: "900",
    fontSize: 14,
  },

  clearButton: {
    alignItems: "center",
    paddingVertical: 13,
  },

  clearButtonText: {
    color: "#B72D59",
    fontWeight: "800",
  },

  checkoutContent: {
    padding: 20,
    paddingBottom: 35,
  },

  checkoutIntro: {
    color: "#806676",
    lineHeight: 20,
    marginBottom: 16,
  },

  savedAddressHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 4,
    marginBottom: 12,
  },

  savedAddressHeading: {
    color: "#351B2A",
    fontSize: 16,
    fontWeight: "900",
  },

  manageAddressText: {
    color: "#C21868",
    fontSize: 12,
    fontWeight: "800",
  },

  addressLoading: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 15,
  },

  addressLoadingText: {
    color: "#806676",
    fontSize: 12,
  },

  savedAddressList: {
    gap: 10,
    marginBottom: 12,
  },

  savedAddressCard: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E9D4E0",
    borderRadius: 14,
    padding: 14,
  },

  savedAddressCardActive: {
    borderColor: "#D63384",
    borderWidth: 2,
    backgroundColor: "#FFF4F8",
  },

  savedAddressTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },

  savedAddressName: {
    color: "#351B2A",
    fontWeight: "900",
    fontSize: 14,
    flex: 1,
  },

  addressRadio: {
    fontSize: 20,
    color: "#BBA4B1",
    marginLeft: 8,
  },

  addressRadioActive: {
    color: "#D63384",
  },

  defaultAddressBadge: {
    color: "#B51D65",
    fontSize: 9,
    fontWeight: "900",
    marginTop: 5,
    marginBottom: 3,
  },

  savedAddressDetails: {
    color: "#806676",
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },

  savedAddressPhone: {
    color: "#806676",
    fontSize: 12,
    marginTop: 6,
  },

  noSavedAddress: {
    backgroundColor: "#FFF0F6",
    borderRadius: 13,
    padding: 14,
    marginBottom: 12,
  },

  noSavedAddressText: {
    color: "#806676",
    fontSize: 12,
    lineHeight: 18,
  },

  addFirstAddressText: {
    color: "#B51D65",
    fontSize: 12,
    fontWeight: "900",
    marginTop: 10,
  },

  fieldLabel: {
    color: "#513347",
    fontSize: 13,
    fontWeight: "800",
    marginBottom: 7,
    marginTop: 12,
  },

  fieldInput: {
    backgroundColor: "#FFFAFC",
    borderWidth: 1,
    borderColor: "#E9D4E0",
    borderRadius: 13,
    paddingHorizontal: 14,
    paddingVertical: 13,
    color: "#351B2A",
    fontSize: 14,
  },

  multilineInput: {
    minHeight: 85,
    textAlignVertical: "top",
  },

  paymentOption: {
    padding: 15,
    borderWidth: 1,
    borderColor: "#E9D4E0",
    borderRadius: 13,
    marginTop: 9,
    backgroundColor: "#FFFFFF",
  },

  paymentOptionActive: {
    borderColor: "#D63384",
    backgroundColor: "#FFF0F6",
  },

  paymentOptionText: {
    color: "#513347",
    fontWeight: "700",
  },

  checkoutTotal: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 18,
    marginTop: 12,
    borderTopWidth: 1,
    borderTopColor: "#F0E1E9",
  },

  checkoutDisclaimer: {
    color: "#998692",
    fontSize: 11,
    lineHeight: 17,
    marginTop: 14,
    textAlign: "center",
  },
});
