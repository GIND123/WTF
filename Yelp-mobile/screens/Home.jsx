import React, { useState, useContext } from 'react';
import { View, Text, TouchableOpacity, StatusBar, Image } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import LoadingScreen from '../components/LoadingScreen';

import { AppContext } from '../context/AppContext';

export default function Home() {
  const navigation = useNavigation();
  const { isLoading } = useContext(AppContext);

  return (
    <View style={{ flex: 1, backgroundColor: '#FFFFFF' }}>
      <StatusBar barStyle="dark-content" backgroundColor="#FFFFFF" />
      <LoadingScreen visible={isLoading} />

      {/* Welcome Screen */}
      <View
        style={{
          flex: 1,
          justifyContent: 'center',
          alignItems: 'center',
          paddingHorizontal: 32,
        }}>
        {/* Title */}
        <Text
          style={{
            fontSize: 32,
            fontWeight: '700',
            color: '#1F2937',
            textAlign: 'center',
            marginBottom: 8,
          }}>
          Welcome to WTF
        </Text>
        <Text
          style={{
            fontSize: 30,
            fontWeight: '700',
            color: '#1F2937',
            textAlign: 'center',
            marginBottom: 8,
          }}>
          (Where is The Food)
        </Text>
        <Text
          style={{
            fontSize: 18,
            color: '#6B7280',
            textAlign: 'center',
            marginBottom: 48,
          }}>
          From your social media feed, to your plate
        </Text>

        <TouchableOpacity
          style={{
            backgroundColor: '#D1252A',
            paddingHorizontal: 48,
            paddingVertical: 16,
            borderRadius: 30,
            shadowColor: '#4CAF50',
            shadowOffset: { width: 0, height: 4 },
            shadowOpacity: 0.3,
            shadowRadius: 8,
            elevation: 6,
            marginBottom: 60,
          }}
          activeOpacity={0.8}
          onPress={() => navigation.navigate('AddPhoto')}>
          <Text
            style={{
              fontSize: 18,
              fontWeight: '600',
              color: '#FFFFFF',
            }}>
            Get Started
          </Text>
        </TouchableOpacity>

        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 24,
          }}>
          <Image
            source={require('../assets/pizza.png')}
            style={{
              width: 90,
              height: 90,
              resizeMode: 'contain',
            }}
          />
          <Image
            source={require('../assets/burger.png')}
            style={{
              width: 90,
              height: 90,
              resizeMode: 'contain',
            }}
          />
          <Image
            source={require('../assets/roasted-chicken.png')}
            style={{
              width: 90,
              height: 90,
              resizeMode: 'contain',
            }}
          />
        </View>
      </View>
    </View>
  );
}
