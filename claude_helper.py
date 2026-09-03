import os
import anthropic
from flask import current_app

class ClaudeAI:
    def __init__(self):
        """Initialize Claude AI client"""
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        self.client = None
        self.model = "claude-sonnet-4-20250514"  # Latest Claude Sonnet 4.5
    
    def _get_client(self):
        """Lazy initialization of client"""
        if self.client is None:
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                raise Exception(f"Failed to initialize Anthropic client: {str(e)}")
        return self.client
    
    def generate_text(self, prompt, max_tokens=1024, temperature=1.0, system_prompt=None):
        """
        Generate text using Claude AI
        
        Args:
            prompt (str): User's input prompt
            max_tokens (int): Maximum tokens to generate
            temperature (float): Creativity level (0.0 to 1.0)
            system_prompt (str): Optional system instructions
        
        Returns:
            str: Generated text response
        """
        try:
            client = self._get_client()
            
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = client.messages.create(**kwargs)
            
            return response.content[0].text
        
        except anthropic.APIError as e:
            if current_app:
                current_app.logger.error(f"Claude API Error: {str(e)}")
            return f"Error: {str(e)}"
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Unexpected error: {str(e)}")
            return f"Unexpected error: {str(e)}"
    
    def chat_conversation(self, messages, max_tokens=2048, temperature=1.0, system_prompt=None):
        """
        Multi-turn conversation with Claude
        
        Args:
            messages (list): List of message dicts with 'role' and 'content'
            max_tokens (int): Maximum tokens to generate
            temperature (float): Creativity level
            system_prompt (str): Optional system instructions
        
        Returns:
            str: Claude's response
        """
        try:
            client = self._get_client()
            
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = client.messages.create(**kwargs)
            
            return response.content[0].text
        
        except anthropic.APIError as e:
            if current_app:
                current_app.logger.error(f"Claude API Error: {str(e)}")
            return f"Error: {str(e)}"
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Unexpected error: {str(e)}")
            return f"Unexpected error: {str(e)}"
    
    def generate_blog_content(self, topic, tone="professional", word_count=500):
        """
        Generate blog post content
        
        Args:
            topic (str): Blog post topic
            tone (str): Writing tone
            word_count (int): Approximate word count
        
        Returns:
            dict: Contains 'title', 'content', 'excerpt'
        """
        system_prompt = f"You are an expert blog writer. Write in a {tone} tone."
        
        prompt = f"""Create a blog post about: {topic}

Requirements:
- Approximately {word_count} words
- Engaging and informative
- Include a catchy title
- Create a brief excerpt (2-3 sentences)
- Use proper formatting with paragraphs

Format your response as:
TITLE: [Blog title here]
EXCERPT: [2-3 sentence excerpt]
CONTENT: [Full blog content]
"""
        
        response = self.generate_text(prompt, max_tokens=4096, system_prompt=system_prompt)
        
        # Parse response
        lines = response.split('\n')
        result = {'title': '', 'excerpt': '', 'content': ''}
        
        current_section = None
        for line in lines:
            if line.startswith('TITLE:'):
                result['title'] = line.replace('TITLE:', '').strip()
                current_section = 'title'
            elif line.startswith('EXCERPT:'):
                result['excerpt'] = line.replace('EXCERPT:', '').strip()
                current_section = 'excerpt'
            elif line.startswith('CONTENT:'):
                current_section = 'content'
            elif current_section == 'content':
                result['content'] += line + '\n'
        
        return result
    
    def analyze_sentiment(self, text):
        """
        Analyze sentiment of text
        
        Returns:
            dict: {'sentiment': 'positive/negative/neutral', 'confidence': float, 'explanation': str}
        """
        prompt = f"""Analyze the sentiment of the following text and respond in this exact format:

SENTIMENT: [positive/negative/neutral]
CONFIDENCE: [0.0 to 1.0]
EXPLANATION: [Brief explanation]

Text to analyze:
{text}
"""
        
        response = self.generate_text(prompt, max_tokens=500)
        
        # Parse response
        result = {'sentiment': 'neutral', 'confidence': 0.5, 'explanation': ''}
        lines = response.split('\n')
        
        for line in lines:
            if line.startswith('SENTIMENT:'):
                result['sentiment'] = line.replace('SENTIMENT:', '').strip().lower()
            elif line.startswith('CONFIDENCE:'):
                try:
                    result['confidence'] = float(line.replace('CONFIDENCE:', '').strip())
                except:
                    result['confidence'] = 0.5
            elif line.startswith('EXPLANATION:'):
                result['explanation'] = line.replace('EXPLANATION:', '').strip()
        
        return result

# Create global instance (without initializing the client yet)
claude_ai = ClaudeAI()