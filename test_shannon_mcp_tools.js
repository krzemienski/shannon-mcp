#!/usr/bin/env node
/**
 * Test Shannon MCP tools using Claude Code SDK
 */

import { CodeSession } from '@anthropic-ai/claude-code-sdk';
import { config } from 'dotenv';

// Load environment variables
config();

async function testShannonMCP() {
  console.log('Testing Shannon MCP tools with Claude Code SDK...\n');
  
  try {
    // Create a new session
    const session = new CodeSession({
      apiKey: process.env.ANTHROPIC_API_KEY,
      model: 'claude-3-sonnet-20241022',
      maxTokens: 4096,
      mcpServers: ['shannon-mcp']
    });
    
    // Test 1: Find Claude Binary
    console.log('=== Test 1: Finding Claude Code binary ===');
    try {
      const binaryResult = await session.callTool('shannon-mcp', 'find_claude_binary', {});
      console.log('Binary found:', JSON.stringify(binaryResult, null, 2));
    } catch (error) {
      console.error('Error finding binary:', error.message);
    }
    
    // Test 2: List Agents
    console.log('\n=== Test 2: Listing available agents ===');
    try {
      const agentsResult = await session.callTool('shannon-mcp', 'list_agents', {});
      console.log('Available agents:', JSON.stringify(agentsResult, null, 2));
    } catch (error) {
      console.error('Error listing agents:', error.message);
    }
    
    // Test 3: Create Session
    console.log('\n=== Test 3: Creating a new session ===');
    try {
      const sessionResult = await session.callTool('shannon-mcp', 'create_session', {
        prompt: 'Test session from Claude Code SDK',
        model: 'claude-3-sonnet',
        context: { test: true, source: 'sdk' }
      });
      console.log('Session created:', JSON.stringify(sessionResult, null, 2));
      
      // Store session ID for further tests
      const sessionId = sessionResult.session_id;
      
      // Test 4: List Sessions
      console.log('\n=== Test 4: Listing sessions ===');
      try {
        const sessionsResult = await session.callTool('shannon-mcp', 'list_sessions', {
          status: 'active',
          limit: 5
        });
        console.log('Active sessions:', JSON.stringify(sessionsResult, null, 2));
      } catch (error) {
        console.error('Error listing sessions:', error.message);
      }
      
    } catch (error) {
      console.error('Error creating session:', error.message);
    }
    
    // Test 5: Access Resources
    console.log('\n=== Test 5: Accessing resources ===');
    
    // Test shannon://config resource
    try {
      const configResource = await session.getResource('shannon-mcp', 'shannon://config');
      console.log('Config resource:', JSON.stringify(configResource, null, 2));
    } catch (error) {
      console.error('Error accessing config resource:', error.message);
    }
    
    // Test shannon://agents resource
    try {
      const agentsResource = await session.getResource('shannon-mcp', 'shannon://agents');
      console.log('\nAgents resource:', JSON.stringify(agentsResource, null, 2));
    } catch (error) {
      console.error('Error accessing agents resource:', error.message);
    }
    
    // Test shannon://sessions resource
    try {
      const sessionsResource = await session.getResource('shannon-mcp', 'shannon://sessions');
      console.log('\nSessions resource:', JSON.stringify(sessionsResource, null, 2));
    } catch (error) {
      console.error('Error accessing sessions resource:', error.message);
    }
    
    console.log('\n✅ All tests completed!');
    
  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

// Run the tests
testShannonMCP();