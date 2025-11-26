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
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as MailComposer from 'expo-mail-composer';
import { Audio } from 'expo-av';

const API_URL = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_PUBLIC_BACKEND_URL;

interface PatientRecord {
  id: number;
  patient_id: string;
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
  needs_backup: boolean;
}

export default function MedicalHistoryApp() {
  const [showWelcome, setShowWelcome] = useState(true);
  const [currentScreen, setCurrentScreen] = useState<'list' | 'form' | 'settings'>('list');
  const [records, setRecords] = useState<PatientRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [storageStats, setStorageStats] = useState<StorageStats | null>(null);
  const [driveConnected, setDriveConnected] = useState(false);
  
  // Form states
  const [patientName, setPatientName] = useState('');
  const [diagnosisDetails, setDiagnosisDetails] = useState('');
  const [medicineNames, setMedicineNames] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isRecording, setIsRecording] = useState(false);

  useEffect(() => {
    fetchRecords();
    fetchStorageStats();
    checkDriveStatus();
    loadCachedRecords();
    
    // Request audio permissions
    Audio.requestPermissionsAsync();
  }, []);

  useEffect(() => {
    if (storageStats && storageStats.needs_backup && driveConnected) {
      Alert.alert(
        'Storage Alert',
        'Storage is 80% full. Automatic backup to Google Drive is recommended.',
        [
          { text: 'Later', style: 'cancel' },
          { text: 'Backup Now', onPress: handleDriveBackup }
        ]
      );
    } else if (storageStats && storageStats.needs_backup && !driveConnected) {
      Alert.alert(
        'Storage Alert',
        'Storage is 80% full. Please connect Google Drive for automatic backup.',
        [
          { text: 'Later', style: 'cancel' },
          { text: 'Connect Drive', onPress: handleConnectDrive }
        ]
      );
    }
  }, [storageStats, driveConnected]);

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

  const checkDriveStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/drive/status`);
      const data = await response.json();
      setDriveConnected(data.connected);
    } catch (error) {
      console.error('Error checking drive status:', error);
    }
  };

  const handleSearch = (text: string) => {
    setSearchQuery(text);
    if (text.length > 2 || text.length === 0) {
      fetchRecords(text);
    }
  };

  const startRecording = async () => {
    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording: newRecording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      setRecording(newRecording);
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to start recording', err);
      Alert.alert('Error', 'Failed to start voice recording');
    }
  };

  const stopRecording = async (field: 'search' | 'name' | 'diagnosis' | 'medicine') => {
    if (!recording) return;

    try {
      setIsRecording(false);
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);

      // For now, show a message that voice-to-text needs configuration
      Alert.alert(
        'Voice Input',
        'Voice-to-text feature requires speech recognition API setup. Would you like to use mock input for demo?',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Use Demo Input',
            onPress: () => {
              const mockInputs = {
                search: 'John Doe',
                name: 'Jane Smith',
                diagnosis: 'Seasonal allergies with mild symptoms',
                medicine: 'Loratadine 10mg once daily'
              };
              
              switch(field) {
                case 'search':
                  handleSearch(mockInputs.search);
                  break;
                case 'name':
                  setPatientName(mockInputs.name);
                  break;
                case 'diagnosis':
                  setDiagnosisDetails(mockInputs.diagnosis);
                  break;
                case 'medicine':
                  setMedicineNames(mockInputs.medicine);
                  break;
              }
            }
          }
        ]
      );
    } catch (error) {
      console.error('Failed to stop recording', error);
    }
  };

  const handleVoiceInput = async (field: 'search' | 'name' | 'diagnosis' | 'medicine') => {
    if (isRecording) {
      await stopRecording(field);
    } else {
      await startRecording();
    }
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

  const handleDelete = async (id: number) => {
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

  const handleConnectDrive = async () => {
    try {
      const response = await fetch(`${API_URL}/api/drive/auth-url`);
      const data = await response.json();
      
      if (data.authorization_url) {
        const supported = await Linking.canOpenURL(data.authorization_url);
        if (supported) {
          await Linking.openURL(data.authorization_url);
        } else {
          Alert.alert('Error', 'Cannot open Google authorization URL');
        }
      }
    } catch (error) {
      console.error('Error connecting to Drive:', error);
      Alert.alert('Error', 'Failed to connect to Google Drive. Please ensure Google OAuth credentials are configured.');
    }
  };

  const handleDriveBackup = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/drive/backup`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const data = await response.json();
        Alert.alert('Success', `Database backed up to Google Drive: ${data.file_name}`);
        fetchStorageStats();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Backup failed');
      }
    } catch (error: any) {
      console.error('Error backing up to Drive:', error);
      Alert.alert('Error', error.message || 'Failed to backup to Google Drive');
    } finally {
      setLoading(false);
    }
  };

  const handleExportEmail = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/export-records`);
      const data = await response.json();
      
      // Format data as CSV
      let csvContent = 'ID,Patient ID,Patient Name,Diagnosis Details,Medicine Names,Created At\n';
      data.records.forEach((record: any) => {
        csvContent += `${record.ID},"${record['Patient ID']}","${record['Patient Name']}","${record['Diagnosis Details']}","${record['Medicine Names']}",${record['Created At']}\n`;
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
          placeholder="Search by patient ID, name, diagnosis..."
          value={searchQuery}
          onChangeText={handleSearch}
        />
        <TouchableOpacity
          style={styles.voiceSearchButton}
          onPress={() => handleVoiceInput('search')}
        >
          <Ionicons
            name={isRecording ? "stop-circle" : "mic"}
            size={24}
            color={isRecording ? "#FF3B30" : "#007AFF"}
          />
        </TouchableOpacity>
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
                <View style={styles.headerLeft}>
                  <View style={styles.patientIdContainer}>
                    <Text style={styles.patientIdText}>{record.patient_id}</Text>
                  </View>
                  <View style={styles.slnoContainer}>
                    <Text style={styles.slnoText}>#{record.id}</Text>
                  </View>
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
              <Ionicons
                name={isRecording ? "stop-circle" : "mic"}
                size={24}
                color={isRecording ? "#FF3B30" : "#007AFF"}
              />
            </TouchableOpacity>
          </View>
          <Text style={styles.helperText}>
            Patient ID will be auto-generated based on name
          </Text>
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
              <Ionicons
                name={isRecording ? "stop-circle" : "mic"}
                size={24}
                color={isRecording ? "#FF3B30" : "#007AFF"}
              />
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
              <Ionicons
                name={isRecording ? "stop-circle" : "mic"}
                size={24}
                color={isRecording ? "#FF3B30" : "#007AFF"}
              />
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.formButtonsContainer}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => {
              resetForm();
              setCurrentScreen('list');
            }}
          >
            <Ionicons name="arrow-back" size={20} color="#007AFF" />
            <Text style={styles.backButtonText}>Back</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.submitButton}
            onPress={handleSubmit}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name="save" size={20} color="#fff" style={styles.buttonIcon} />
                <Text style={styles.submitButtonText}>
                  {editingId ? 'Update Record' : 'Save Record'}
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>
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

            {storageStats.needs_backup && (
              <View style={styles.warningBanner}>
                <Ionicons name="warning" size={20} color="#FF3B30" />
                <Text style={styles.warningText}>
                  Storage is {storageStats.storage_percentage}% full. Backup recommended!
                </Text>
              </View>
            )}
          </View>
        )}

        <Text style={styles.sectionTitle}>Google Drive</Text>
        
        <View style={styles.driveStatusCard}>
          <Ionicons
            name={driveConnected ? "cloud-done" : "cloud-offline"}
            size={32}
            color={driveConnected ? "#34C759" : "#8E8E93"}
          />
          <View style={styles.driveStatusText}>
            <Text style={styles.driveStatusTitle}>
              {driveConnected ? 'Connected' : 'Not Connected'}
            </Text>
            <Text style={styles.driveStatusSubtitle}>
              {driveConnected
                ? 'Automatic backup enabled at 80%'
                : 'Connect to enable automatic backup'}
            </Text>
          </View>
        </View>

        {!driveConnected && (
          <TouchableOpacity style={styles.settingsButton} onPress={handleConnectDrive}>
            <Ionicons name="logo-google" size={24} color="#007AFF" />
            <View style={styles.settingsButtonText}>
              <Text style={styles.settingsButtonTitle}>Connect Google Drive</Text>
              <Text style={styles.settingsButtonSubtitle}>Enable automatic cloud backup</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color="#C7C7CC" />
          </TouchableOpacity>
        )}

        {driveConnected && (
          <TouchableOpacity style={styles.settingsButton} onPress={handleDriveBackup}>
            <Ionicons name="cloud-upload" size={24} color="#007AFF" />
            <View style={styles.settingsButtonText}>
              <Text style={styles.settingsButtonTitle}>Backup to Google Drive</Text>
              <Text style={styles.settingsButtonSubtitle}>Manual backup now</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color="#C7C7CC" />
          </TouchableOpacity>
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
            checkDriveStatus();
            Alert.alert('Success', 'Data refreshed');
          }}
        >
          <Ionicons name="refresh" size={24} color="#007AFF" />
          <View style={styles.settingsButtonText}>
            <Text style={styles.settingsButtonTitle}>Refresh Data</Text>
            <Text style={styles.settingsButtonSubtitle}>Sync with storage</Text>
          </View>
          <Ionicons name="chevron-forward" size={24} color="#C7C7CC" />
        </TouchableOpacity>
      </ScrollView>
    </View>
  );

  // Welcome screen render
  const renderWelcomeScreen = () => (
    <View style={styles.welcomeContainer}>
      <ScrollView 
        contentContainerStyle={styles.welcomeContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.welcomeIconContainer}>
          <Ionicons name="medical" size={80} color="#007AFF" />
          <View style={styles.heartbeatLine} />
        </View>

        <Text style={styles.welcomeTitle}>Welcome to Your Personal</Text>
        <Text style={styles.welcomeTitleHighlight}>Medical History App</Text>

        <View style={styles.welcomeCard}>
          <Text style={styles.welcomeText}>
            Thoughtfully maintained by <Text style={styles.maintainerName}>Binod Kumar</Text>.
          </Text>
          
          <Text style={styles.welcomeDescription}>
            This app is designed to make managing your health records simple, secure, and always within reach. 
            Whether you're tracking past treatments, storing prescriptions, or maintaining important notes, 
            everything is organized in one place for quick access.
          </Text>

          <Text style={styles.welcomeDescription}>
            With a focus on ease of use and accuracy, Binod Kumar ensures that your medical information is 
            kept up-to-date and accessible whenever you need it.
          </Text>

          <View style={styles.welcomeHighlight}>
            <Ionicons name="heart" size={20} color="#FF3B30" />
            <Text style={styles.welcomeHighlightText}>
              Your health journey matters — and this app is here to help you manage it effortlessly.
            </Text>
          </View>
        </View>

        <TouchableOpacity 
          style={styles.enterButton}
          onPress={() => setShowWelcome(false)}
          activeOpacity={0.8}
        >
          <Ionicons name="enter" size={24} color="#fff" style={styles.enterIcon} />
          <Text style={styles.enterButtonText}>Enter Medical History Section</Text>
          <Ionicons name="arrow-forward" size={24} color="#fff" />
        </TouchableOpacity>

        <View style={styles.welcomeFeatures}>
          <View style={styles.featureItem}>
            <Ionicons name="shield-checkmark" size={24} color="#34C759" />
            <Text style={styles.featureText}>Secure Storage</Text>
          </View>
          <View style={styles.featureItem}>
            <Ionicons name="cloud-upload" size={24} color="#007AFF" />
            <Text style={styles.featureText}>Cloud Backup</Text>
          </View>
          <View style={styles.featureItem}>
            <Ionicons name="mic" size={24} color="#FF9500" />
            <Text style={styles.featureText}>Voice Input</Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );

  // Show welcome screen or main app
  if (showWelcome) {
    return (
      <SafeAreaView style={styles.container}>
        {renderWelcomeScreen()}
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Ionicons name="medical" size={28} color="#007AFF" />
        <Text style={styles.headerTitle}>Medical History</Text>
        {driveConnected && (
          <Ionicons name="cloud-done" size={20} color="#34C759" style={styles.headerDriveIcon} />
        )}
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
  // Welcome Screen Styles
  welcomeContainer: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  welcomeContent: {
    flexGrow: 1,
    padding: 24,
    paddingTop: 40,
    alignItems: 'center',
  },
  welcomeIconContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  heartbeatLine: {
    width: 60,
    height: 3,
    backgroundColor: '#007AFF',
    marginTop: 12,
    borderRadius: 2,
  },
  welcomeTitle: {
    fontSize: 24,
    fontWeight: '600',
    color: '#000',
    textAlign: 'center',
    marginBottom: 4,
  },
  welcomeTitleHighlight: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
    textAlign: 'center',
    marginBottom: 32,
  },
  welcomeCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 24,
    marginBottom: 32,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  welcomeText: {
    fontSize: 16,
    color: '#000',
    lineHeight: 24,
    marginBottom: 16,
    textAlign: 'center',
  },
  maintainerName: {
    fontWeight: 'bold',
    color: '#007AFF',
  },
  welcomeDescription: {
    fontSize: 15,
    color: '#333',
    lineHeight: 22,
    marginBottom: 16,
    textAlign: 'justify',
  },
  welcomeHighlight: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF3E0',
    padding: 16,
    borderRadius: 12,
    marginTop: 8,
  },
  welcomeHighlightText: {
    fontSize: 15,
    color: '#000',
    fontWeight: '600',
    marginLeft: 12,
    flex: 1,
    lineHeight: 20,
  },
  enterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    paddingVertical: 18,
    paddingHorizontal: 32,
    borderRadius: 16,
    marginBottom: 32,
    width: '100%',
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  enterIcon: {
    marginRight: 12,
  },
  enterButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
    flex: 1,
    textAlign: 'center',
  },
  welcomeFeatures: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
    paddingHorizontal: 16,
  },
  featureItem: {
    alignItems: 'center',
  },
  featureText: {
    fontSize: 12,
    color: '#666',
    marginTop: 8,
    fontWeight: '600',
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
  headerDriveIcon: {
    position: 'absolute',
    right: 16,
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
  voiceSearchButton: {
    padding: 8,
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
  headerLeft: {
    flexDirection: 'row',
    gap: 8,
  },
  patientIdContainer: {
    backgroundColor: '#34C759',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  patientIdText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 14,
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
  helperText: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
    fontStyle: 'italic',
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
  formButtonsContainer: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff',
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#007AFF',
    minWidth: 100,
  },
  backButtonText: {
    color: '#007AFF',
    fontSize: 17,
    fontWeight: '600',
    marginLeft: 8,
  },
  submitButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    paddingVertical: 16,
    borderRadius: 12,
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '600',
  },
  buttonIcon: {
    marginRight: 8,
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
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#000',
    marginTop: 24,
    marginBottom: 16,
  },
  storageCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 8,
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
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFE5E5',
    padding: 12,
    borderRadius: 8,
    marginTop: 16,
  },
  warningText: {
    fontSize: 14,
    color: '#FF3B30',
    fontWeight: '600',
    marginLeft: 8,
    flex: 1,
  },
  driveStatusCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  driveStatusText: {
    flex: 1,
    marginLeft: 12,
  },
  driveStatusTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#000',
  },
  driveStatusSubtitle: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
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