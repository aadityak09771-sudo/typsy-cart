
import React, { useEffect, useState } from "react";
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
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
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useRouter } from "expo-router";

const STORAGE_KEY = "@tipsy_cart_saved_addresses_v1";

type Address = {
  id: string;
  full_name: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  isDefault: boolean;
};

const EMPTY_ADDRESS = {
  full_name: "",
  phone: "",
  address: "",
  city: "Kanpur",
  state: "Uttar Pradesh",
  pincode: "",
};

export default function AddressesScreen() {
  const router = useRouter();

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);
  const [formVisible, setFormVisible] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_ADDRESS);

  useEffect(() => {
    loadAddresses();
  }, []);

  async function loadAddresses() {
    try {
      const saved = await AsyncStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          setAddresses(parsed);
        }
      }
    } catch {
      Alert.alert("Error", "Addresses load nahi ho paaye.");
    } finally {
      setLoading(false);
    }
  }

  async function saveAddresses(updated: Address[]) {
    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      setAddresses(updated);
    } catch {
      Alert.alert("Error", "Address save nahi ho paaya.");
    }
  }

  function updateField(field: keyof typeof EMPTY_ADDRESS, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function openAddForm() {
    setEditingId(null);
    setForm({ ...EMPTY_ADDRESS });
    setFormVisible(true);
  }

  function openEditForm(item: Address) {
    setEditingId(item.id);
    setForm({
      full_name: item.full_name,
      phone: item.phone,
      address: item.address,
      city: item.city,
      state: item.state,
      pincode: item.pincode,
    });
    setFormVisible(true);
  }

  async function handleSave() {
    const name = form.full_name.trim();
    const phone = form.phone.replace(/\D/g, "");
    const address = form.address.trim();
    const city = form.city.trim();
    const state = form.state.trim();
    const pincode = form.pincode.trim();

    if (!name || !phone || !address || !city || !state || !pincode) {
      Alert.alert("Missing details", "Saari details fill karo.");
      return;
    }

    if (name.length > 150 || address.length > 255) {
      Alert.alert("Invalid details", "Name ya address bahut lamba hai.");
      return;
    }

    if (!/^[6-9]\d{9}$/.test(phone)) {
      Alert.alert("Invalid phone", "Valid 10-digit mobile number enter karo.");
      return;
    }

    if (!/^\d{6}$/.test(pincode)) {
      Alert.alert("Invalid pincode", "6-digit pincode enter karo.");
      return;
    }

    let updated: Address[];

    if (editingId) {
      updated = addresses.map((item) =>
        item.id === editingId
          ? { ...item, ...form, full_name: name, phone, address, city, state, pincode }
          : item
      );
    } else {
      updated = [
        ...addresses,
        {
          id: `${Date.now()}`,
          full_name: name,
          phone,
          address,
          city,
          state,
          pincode,
          isDefault: addresses.length === 0,
        },
      ];
    }

    await saveAddresses(updated);
    setFormVisible(false);
    setEditingId(null);
    setForm({ ...EMPTY_ADDRESS });
    Alert.alert("Success", "Address save ho gaya!");
  }

  async function makeDefault(id: string) {
    const updated = addresses.map((item) => ({
      ...item,
      isDefault: item.id === id,
    }));
    await saveAddresses(updated);
  }

  function deleteAddress(id: string) {
    Alert.alert("Delete address?", "Kya tum ye address delete karna chahte ho?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () => {
          const remaining = addresses.filter((item) => item.id !== id);

          if (remaining.length > 0 && !remaining.some((item) => item.isDefault)) {
            remaining[0].isDefault = true;
          }

          void saveAddresses(remaining);
        },
      },
    ]);
  }

  function renderAddress({ item }: { item: Address }) {
    return (
      <View style={styles.addressCard}>
        <View style={styles.cardTop}>
          <Text style={styles.name}>{item.full_name}</Text>
          {item.isDefault && (
            <Text style={styles.defaultBadge}>DEFAULT</Text>
          )}
        </View>

        <Text style={styles.detail}>{item.phone}</Text>
        <Text style={styles.detail}>{item.address}</Text>
        <Text style={styles.detail}>
          {item.city}, {item.state} - {item.pincode}
        </Text>

        <View style={styles.actions}>
          {!item.isDefault && (
            <Pressable onPress={() => void makeDefault(item.id)}>
              <Text style={styles.actionText}>Make Default</Text>
            </Pressable>
          )}
          <Pressable onPress={() => openEditForm(item)}>
            <Text style={styles.actionText}>Edit</Text>
          </Pressable>
          <Pressable onPress={() => deleteAddress(item.id)}>
            <Text style={styles.deleteText}>Delete</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />

      <View style={styles.header}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.back}>‹</Text>
        </Pressable>
        <Text style={styles.title}>Saved Addresses</Text>
        <View style={{ width: 25 }} />
      </View>

      {!formVisible ? (
        <>
          <View style={styles.intro}>
            <Text style={styles.introTitle}>Your delivery locations</Text>
            <Text style={styles.introText}>
              Save your addresses for a faster checkout.
            </Text>
          </View>

          <Pressable style={styles.addButton} onPress={openAddForm}>
            <Text style={styles.addButtonText}>＋ Add New Address</Text>
          </Pressable>

          {loading ? (
            <Text style={styles.emptyText}>Loading addresses...</Text>
          ) : (
            <FlatList
              data={addresses}
              keyExtractor={(item) => item.id}
              renderItem={renderAddress}
              contentContainerStyle={styles.list}
              ListEmptyComponent={
                <View style={styles.empty}>
                  <Text style={styles.emptyEmoji}>📍</Text>
                  <Text style={styles.emptyTitle}>No saved addresses</Text>
                  <Text style={styles.emptyText}>
                    Add your first delivery address.
                  </Text>
                </View>
              }
            />
          )}
        </>
      ) : (
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <ScrollView
            contentContainerStyle={styles.formContent}
            keyboardShouldPersistTaps="handled"
          >
            <Text style={styles.formTitle}>
              {editingId ? "Edit Address" : "Add New Address"}
            </Text>

            {(
              [
                ["full_name", "Full Name", "Your full name"],
                ["phone", "Mobile Number", "10-digit mobile number"],
                ["address", "Full Address", "House number, street, area"],
                ["city", "City", "City"],
                ["state", "State", "State"],
                ["pincode", "Pincode", "6-digit pincode"],
              ] as const
            ).map(([field, label, placeholder]) => (
              <View key={field}>
                <Text style={styles.label}>{label} *</Text>
                <TextInput
                  style={[
                    styles.input,
                    field === "address" && styles.multiline,
                  ]}
                  value={form[field]}
                  onChangeText={(value) => {
                    if (field === "phone") {
                      updateField(field, value.replace(/\D/g, "").slice(0, 10));
                    } else if (field === "pincode") {
                      updateField(field, value.replace(/\D/g, "").slice(0, 6));
                    } else {
                      updateField(field, value);
                    }
                  }}
                  placeholder={placeholder}
                  keyboardType={
                    field === "phone"
                      ? "phone-pad"
                      : field === "pincode"
                      ? "number-pad"
                      : "default"
                  }
                  multiline={field === "address"}
                  maxLength={
                    field === "phone" ? 10 :
                    field === "pincode" ? 6 :
                    field === "full_name" ? 150 :
                    field === "address" ? 255 : 100
                  }
                  autoCapitalize={field === "full_name" ? "words" : "sentences"}
                />
              </View>
            ))}

            <Pressable style={styles.addButton} onPress={() => void handleSave()}>
              <Text style={styles.addButtonText}>Save Address</Text>
            </Pressable>

            <Pressable
              style={styles.cancelButton}
              onPress={() => setFormVisible(false)}
            >
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
          </ScrollView>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#FFF8FA" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 18,
    borderBottomWidth: 1,
    borderBottomColor: "#F1DFE8",
  },
  back: { fontSize: 32, color: "#C21868" },
  title: { fontSize: 20, fontWeight: "900", color: "#351B2A" },
  intro: { padding: 20, paddingBottom: 8 },
  introTitle: { fontSize: 19, fontWeight: "900", color: "#351B2A" },
  introText: { color: "#806676", marginTop: 6, fontSize: 13 },
  addButton: {
    backgroundColor: "#D63384",
    padding: 15,
    borderRadius: 14,
    alignItems: "center",
    marginHorizontal: 20,
    marginVertical: 12,
  },
  addButtonText: { color: "#FFFFFF", fontWeight: "900", fontSize: 14 },
  list: { padding: 20, paddingTop: 5, paddingBottom: 35 },
  addressCard: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#F0DFE8",
    borderRadius: 17,
    padding: 16,
    marginBottom: 13,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  name: { color: "#351B2A", fontSize: 16, fontWeight: "900", flex: 1 },
  defaultBadge: {
    color: "#B71F68",
    backgroundColor: "#FCE4EF",
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: 8,
    fontSize: 9,
    fontWeight: "900",
  },
  detail: { color: "#806676", fontSize: 13, lineHeight: 21 },
  actions: {
    flexDirection: "row",
    gap: 22,
    marginTop: 15,
    flexWrap: "wrap",
  },
  actionText: { color: "#C21868", fontWeight: "800", fontSize: 12 },
  deleteText: { color: "#C02D59", fontWeight: "800", fontSize: 12 },
  empty: { alignItems: "center", padding: 35 },
  emptyEmoji: { fontSize: 45 },
  emptyTitle: {
    color: "#351B2A",
    fontSize: 17,
    fontWeight: "900",
    marginTop: 12,
  },
  emptyText: { color: "#806676", textAlign: "center", marginTop: 8 },
  formContent: { padding: 20, paddingBottom: 40 },
  formTitle: {
    fontSize: 21,
    fontWeight: "900",
    color: "#351B2A",
    marginBottom: 12,
  },
  label: {
    color: "#513347",
    fontSize: 13,
    fontWeight: "800",
    marginTop: 13,
    marginBottom: 7,
  },
  input: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E9D4E0",
    borderRadius: 13,
    padding: 14,
    color: "#351B2A",
    fontSize: 14,
  },
  multiline: { minHeight: 85, textAlignVertical: "top" },
  cancelButton: { alignItems: "center", padding: 14 },
  cancelText: { color: "#8D5471", fontWeight: "800" },
});
