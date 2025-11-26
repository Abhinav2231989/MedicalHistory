import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ScrollView,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Speech from 'expo-speech';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as MailComposer from 'expo-mail-composer';

const API_URL = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_PUBLIC_BACKEND_URL;

interface PatientRecord {
  id: string;
  slno: number;
  patient_name: string;
  diagnosis_details: string;
  medicine_names: string;
  created_at: string;
  updated_at: string;
}

interface StorageStats {
  total_records: number;
  storage_used_mb: number;
  storage_percentage: number;
}

export default function MedicalHistoryApp() {
  const [currentScreen, setCurrentScreen] = useState<'list' | 'form' | 'settings'>('list');
  const [records, setRecords] = useState<PatientRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [storageStats, setStorageStats] = useState<StorageStats | null>(null);
  
  // Form states
  const [patientName, setPatientName] = useState('');
  const [diagnosisDetails, setDiagnosisDetails] = useState('');
  const [medicineNames, setMedicineNames] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState<string | null>(null);

  useEffect(() => {
    fetchRecords();
    fetchStorageStats();
    loadCachedRecords();
  }, []);

  useEffect(() => {
    if (storageStats && storageStats.storage_percentage >= 80) {
      Alert.alert(
        'Storage Alert',
        'Storage is 80% full. Would you like to backup your data via email?',
        [
          { text: 'Later', style: 'cancel' },
          { text: 'Backup Now', onPress: handleExportEmail }
        ]
      );
    }
  }, [storageStats]);

  const loadCachedRecords = async () => {
    try {
      const cached = await AsyncStorage.getItem('patient_records');
      if (cached) {
        setRecords(JSON.parse(cached));
      }
    } catch (error) {
      console.error('Error loading cached records:', error);
    }
  };

  const cacheRecords = async (data: PatientRecord[]) => {
    try {
      await AsyncStorage.setItem('patient_records', JSON.stringify(data));
    } catch (error) {
      console.error('Error caching records:', error);
    }
  };

  const fetchRecords = async (search?: string) => {
    try {
      setLoading(true);
      const url = search
        ? `${API_URL}/api/patients?search=${encodeURIComponent(search)}`
        : `${API_URL}/api/patients`;
      
      const response = await fetch(url);
      const data = await response.json();
      setRecords(data);
      await cacheRecords(data);
    } catch (error) {
      console.error('Error fetching records:', error);
      Alert.alert('Error', 'Failed to fetch records. Using cached data.');
    } finally {
      setLoading(false);
    }
  };

  const fetchStorageStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/storage-stats`);
      const data = await response.json();
      setStorageStats(data);
    } catch (error) {
      console.error('Error fetching storage stats:', error);
    }
  };

  const handleSearch = (text: string) => {
    setSearchQuery(text);
    if (text.length > 2 || text.length === 0) {
      fetchRecords(text);
    }
  };

  const handleVoiceInput = async (field: 'name' | 'diagnosis' | 'medicine') => {
    // Note: expo-speech is for text-to-speech, not speech-to-text
    // For actual voice input, we would need expo-speech-recognition or a cloud service
    // For now, showing placeholder functionality
    Alert.alert(
      'Voice Input',
      'Please speak your input. (Voice recognition would be integrated here with a speech-to-text service)',
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Simulate Input',
          onPress: () => {
            const mockInput = {
              name: 'John Doe',
              diagnosis: 'Common cold with fever',
              medicine: 'Paracetamol, Vitamin C'
            };
            
            switch(field) {
              case 'name':
                setPatientName(mockInput.name);
                break;
              case 'diagnosis':
                setDiagnosisDetails(mockInput.diagnosis);
                break;
              case 'medicine':
                setMedicineNames(mockInput.medicine);
                break;
            }
          }
        }
      ]
    );
  };

  const handleSubmit = async () => {
    if (!patientName || !diagnosisDetails || !medicineNames) {
      Alert.alert('Error', 'Please fill all fields');
      return;
    }

    try {
      setLoading(true);
      const url = editingId
        ? `${API_URL}/api/patients/${editingId}`
        : `${API_URL}/api/patients`;
      
      const method = editingId ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          patient_name: patientName,
          diagnosis_details: diagnosisDetails,
          medicine_names: medicineNames,
        }),
      });

      if (response.ok) {
        Alert.alert('Success', `Record ${editingId ? 'updated' : 'created'} successfully`);
        resetForm();
        fetchRecords();
        fetchStorageStats();
        setCurrentScreen('list');
      } else {
        throw new Error('Failed to save record');
      }
    } catch (error) {
      console.error('Error saving record:', error);
      Alert.alert('Error', 'Failed to save record');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (record: PatientRecord) => {
    setEditingId(record.id);
    setPatientName(record.patient_name);
    setDiagnosisDetails(record.diagnosis_details);
    setMedicineNames(record.medicine_names);
    setCurrentScreen('form');
  };

  const handleDelete = async (id: string) => {
    Alert.alert(
      'Confirm Delete',
      'Are you sure you want to delete this record?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              setLoading(true);
              const response = await fetch(`${API_URL}/api/patients/${id}`, {
                method: 'DELETE',
              });

              if (response.ok) {
                Alert.alert('Success', 'Record deleted successfully');
                fetchRecords();
                fetchStorageStats();
              } else {
                throw new Error('Failed to delete record');
              }
            } catch (error) {
              console.error('Error deleting record:', error);
              Alert.alert('Error', 'Failed to delete record');
            } finally {
              setLoading(false);
            }
          },
        },
      ]
    );
  };

  const resetForm = () => {
    setPatientName('');
    setDiagnosisDetails('');
    setMedicineNames('');
    setEditingId(null);
  };

  const handleExportEmail = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/export-records`);
      const data = await response.json();
      
      // Format data as CSV
      let csvContent = 'SlNo,Patient Name,Diagnosis Details,Medicine Names,Created At\n';
      data.records.forEach((record: any) => {
        csvContent += `${record.SlNo},"${record['Patient Name']}","${record['Diagnosis Details']}","${record['Medicine Names']}",${record['Created At']}\n`;
      });

      const isAvailable = await MailComposer.isAvailableAsync();
      if (isAvailable) {
        await MailComposer.composeAsync({
          subject: 'Medical History Records Backup',
          body: `Medical History System Backup\n\nTotal Records: ${data.total}\n\nCSV Data:\n${csvContent}`,
          recipients: [],
        });
      } else {
        Alert.alert('Error', 'Email composer is not available on this device');
      }
    } catch (error) {
      console.error('Error exporting records:', error);
      Alert.alert('Error', 'Failed to export records');
    } finally {
      setLoading(false);
    }
  };

  const renderListScreen = () => (
    <View style={styles.screen}>
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#666" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search patients, diagnosis, or medicines..."
          value={searchQuery}
          onChangeText={handleSearch}
        />
      </View>

      {loading && records.length === 0 ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : records.length === 0 ? (
        <View style={styles.centerContainer}>
          <Ionicons name="document-text-outline" size={64} color="#ccc" />
          <Text style={styles.emptyText}>No records yet</Text>
          <Text style={styles.emptySubtext}>Tap + to add your first patient record</Text>
        </View>
      ) : (
        <ScrollView style={styles.listContainer}>
          {records.map((record) => (
            <View key={record.id} style={styles.recordCard}>
              <View style={styles.recordHeader}>
                <View style={styles.slnoContainer}>
                  <Text style={styles.slnoText}>#{record.slno}</Text>
                </View>
                <View style={styles.recordActions}>
                  <TouchableOpacity onPress={() => handleEdit(record)} style={styles.actionButton}>
                    <Ionicons name="pencil" size={20} color="#007AFF" />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => handleDelete(record.id)} style={styles.actionButton}>
                    <Ionicons name="trash" size={20} color="#FF3B30" />
                  </TouchableOpacity>
                </View>
              </View>
              
              <Text style={styles.patientName}>{record.patient_name}</Text>
              
              <View style={styles.recordSection}>
                <Text style={styles.recordLabel}>Diagnosis:</Text>
                <Text style={styles.recordValue}>{record.diagnosis_details}</Text>
              </View>
              
              <View style={styles.recordSection}>
                <Text style={styles.recordLabel}>Medicines:</Text>
                <Text style={styles.recordValue}>{record.medicine_names}</Text>
              </View>
              
              <Text style={styles.recordDate}>
                {new Date(record.created_at).toLocaleDateString()}
              </Text>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );

  const renderFormScreen = () => (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.screen}
    >
      <ScrollView style={styles.formContainer}>
        <Text style={styles.formTitle}>
          {editingId ? 'Edit Record' : 'Add New Record'}
        </Text>

        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Patient Name</Text>
          <View style={styles.inputWithVoice}>
            <TextInput
              style={styles.textInput}
              placeholder="Enter patient name"
              value={patientName}
              onChangeText={setPatientName}
            />
            <TouchableOpacity
              style={styles.voiceButton}
              onPress={() => handleVoiceInput('name')}
            >
              <Ionicons name="mic" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Diagnosis Details</Text>
          <View style={styles.inputWithVoice}>
            <TextInput
              style={[styles.textInput, styles.textArea]}
              placeholder="Enter diagnosis details"
              value={diagnosisDetails}
              onChangeText={setDiagnosisDetails}
              multiline
              numberOfLines={4}
            />
            <TouchableOpacity
              style={[styles.voiceButton, styles.voiceButtonTop]}
              onPress={() => handleVoiceInput('diagnosis')}
            >
              <Ionicons name="mic" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Medicine Names</Text>
          <View style={styles.inputWithVoice}>
            <TextInput
              style={[styles.textInput, styles.textArea]}
              placeholder="Enter medicine names"
              value={medicineNames}
              onChangeText={setMedicineNames}
              multiline
              numberOfLines={3}
            />
            <TouchableOpacity
              style={[styles.voiceButton, styles.voiceButtonTop]}
              onPress={() => handleVoiceInput('medicine')}
            >
              <Ionicons name="mic" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
        </View>

        <TouchableOpacity
          style={styles.submitButton}
          onPress={handleSubmit}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitButtonText}>
              {editingId ? 'Update Record' : 'Save Record'}
            </Text>
          )}
        </TouchableOpacity>

        {editingId && (
          <TouchableOpacity
            style={styles.cancelButton}
            onPress={() => {
              resetForm();
              setCurrentScreen('list');
            }}
          >
            <Text style={styles.cancelButtonText}>Cancel</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );

  const renderSettingsScreen = () => (
    <View style={styles.screen}>
      <ScrollView style={styles.settingsContainer}>
        <Text style={styles.settingsTitle}>Storage & Backup</Text>

        {storageStats && (
          <View style={styles.storageCard}>
            <View style={styles.storageHeader}>
              <Ionicons name="server" size={32} color="#007AFF" />
              <Text style={styles.storageTitle}>Storage Usage</Text>
            </View>
            
            <View style={styles.storageBar}>
              <View
                style={[
                  styles.storageBarFill,
                  {
                    width: `${Math.min(storageStats.storage_percentage, 100)}%`,
                    backgroundColor:
                      storageStats.storage_percentage >= 80
                        ? '#FF3B30'
                        : storageStats.storage_percentage >= 60
                        ? '#FF9500'
                        : '#34C759',
                  },
                ]}
              />
            </View>
            
            <View style={styles.storageStats}>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{storageStats.total_records}</Text>
                <Text style={styles.statLabel}>Total Records</Text>
              </View>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{storageStats.storage_used_mb} MB</Text>
                <Text style={styles.statLabel}>Storage Used</Text>
              </View>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{storageStats.storage_percentage}%</Text>
                <Text style={styles.statLabel}>Usage</Text>
              </View>
            </View>
          </View>
        )}

        <TouchableOpacity style={styles.settingsButton} onPress={handleExportEmail}>
          <Ionicons name="mail" size={24} color="#007AFF" />
          <View style={styles.settingsButtonText}>
            <Text style={styles.settingsButtonTitle}>Export via Email</Text>
            <Text style={styles.settingsButtonSubtitle}>Send all records to your email</Text>
          </View>
          <Ionicons name="chevron-forward" size={24} color="#C7C7CC" />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.settingsButton}
          onPress={() => {
            fetchRecords();
            fetchStorageStats();
            Alert.alert('Success', 'Data refreshed');
          }}
        >
          <Ionicons name="refresh" size={24} color="#007AFF" />
          <View style={styles.settingsButtonText}>
            <Text style={styles.settingsButtonTitle}>Refresh Data</Text>
            <Text style={styles.settingsButtonSubtitle}>Sync with server</Text>
          </View>
          <Ionicons name="chevron-forward" size={24} color="#C7C7CC" />
        </TouchableOpacity>
      </ScrollView>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Ionicons name="medical" size={28} color="#007AFF" />
        <Text style={styles.headerTitle}>Medical History</Text>
      </View>

      {currentScreen === 'list' && renderListScreen()}
      {currentScreen === 'form' && renderFormScreen()}
      {currentScreen === 'settings' && renderSettingsScreen()}

      <View style={styles.tabBar}>
        <TouchableOpacity
          style={styles.tabItem}
          onPress={() => setCurrentScreen('list')}
        >
          <Ionicons
            name={currentScreen === 'list' ? 'list' : 'list-outline'}
            size={28}
            color={currentScreen === 'list' ? '#007AFF' : '#8E8E93'}
          />
          <Text
            style={[
              styles.tabLabel,
              currentScreen === 'list' && styles.tabLabelActive,
            ]}
          >
            Records
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.addButton}
          onPress={() => {
            resetForm();
            setCurrentScreen('form');
          }}
        >
          <Ionicons name="add" size={32} color="#fff" />
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.tabItem}
          onPress={() => setCurrentScreen('settings')}
        >
          <Ionicons
            name={currentScreen === 'settings' ? 'settings' : 'settings-outline'}
            size={28}
            color={currentScreen === 'settings' ? '#007AFF' : '#8E8E93'}
          />
          <Text
            style={[
              styles.tabLabel,
              currentScreen === 'settings' && styles.tabLabelActive,
            ]}
          >
            Settings
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E5EA',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#000',
    marginLeft: 8,
  },
  screen: {
    flex: 1,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    margin: 16,
    paddingHorizontal: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E5EA',
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 12,
    fontSize: 16,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyText: {
    fontSize: 20,
    fontWeight: '600',
    color: '#000',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
  listContainer: {
    flex: 1,
    paddingHorizontal: 16,
  },
  recordCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  recordHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  slnoContainer: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  slnoText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 14,
  },
  recordActions: {
    flexDirection: 'row',
  },
  actionButton: {
    padding: 8,
    marginLeft: 8,
  },
  patientName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#000',
    marginBottom: 12,
  },
  recordSection: {
    marginBottom: 8,
  },
  recordLabel: {
    fontSize: 12,
    color: '#8E8E93',
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  recordValue: {
    fontSize: 15,
    color: '#000',
    lineHeight: 20,
  },
  recordDate: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 8,
  },
  formContainer: {
    flex: 1,
    padding: 16,
  },
  formTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#000',
    marginBottom: 24,
  },
  inputGroup: {
    marginBottom: 24,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#000',
    marginBottom: 8,
  },
  inputWithVoice: {
    position: 'relative',
  },
  textInput: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#E5E5EA',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    paddingRight: 56,
  },
  textArea: {
    minHeight: 100,
    textAlignVertical: 'top',
    paddingTop: 12,
  },
  voiceButton: {
    position: 'absolute',
    right: 12,
    top: 12,
    padding: 8,
  },
  voiceButtonTop: {
    top: 12,
  },
  submitButton: {
    backgroundColor: '#007AFF',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '600',
  },
  cancelButton: {
    backgroundColor: '#fff',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#E5E5EA',
  },
  cancelButtonText: {
    color: '#007AFF',
    fontSize: 17,
    fontWeight: '600',
  },
  settingsContainer: {
    flex: 1,
    padding: 16,
  },
  settingsTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#000',
    marginBottom: 24,
  },
  storageCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  storageHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  storageTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#000',
    marginLeft: 12,
  },
  storageBar: {
    height: 8,
    backgroundColor: '#E5E5EA',
    borderRadius: 4,
    marginBottom: 16,
    overflow: 'hidden',
  },
  storageBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  storageStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  statItem: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#000',
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
  settingsButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  settingsButtonText: {
    flex: 1,
    marginLeft: 12,
  },
  settingsButtonTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  settingsButtonSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#E5E5EA',
    paddingBottom: 8,
    paddingTop: 8,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabLabel: {
    fontSize: 11,
    color: '#8E8E93',
    marginTop: 4,
  },
  tabLabelActive: {
    color: '#007AFF',
    fontWeight: '600',
  },
  addButton: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -20,
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
});