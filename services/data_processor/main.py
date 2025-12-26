"""
Data Processor Service - Processes S3 events from SQS, downloads and validates movie data
"""
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

# Add shared modules to path
sys.path.append('..')
from shared import Movie, config

# Import services from API (reusing database components)
sys.path.append('../api')
from shared.database import Database
from shared.repositories import MovieRepository

logger = logging.getLogger(__name__)


class DataProcessor:
    """Processes validated movie data from SQS"""
    
    def __init__(self):
        self.config = config
        self.sqs_client = boto3.client('sqs', region_name=self.config.aws.region)
        self.s3_client = boto3.client('s3', region_name=self.config.aws.region)
        
        # Initialize database service
        self.database = Database(self.config.database)
        self.movie_repo = None
        
        # Processing state
        self.is_running = False
        self.processed_count = 0
        self.error_count = 0
    
    async def start(self):
        """Start the data processor"""
        logger.info("🚀 Starting Movie Data Processor...")
        
        # Initialize services
        await self.database.connect()
        self.movie_repo = MovieRepository(self.database)
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.is_running = True
        logger.info("✅ Data processor started successfully")
        
        # Start processing loop
        await self._process_messages()
    
    async def stop(self):
        """Stop the data processor"""
        logger.info("🛑 Stopping Movie Data Processor...")
        self.is_running = False
        
        # Cleanup
        await self.database.disconnect()
        
        logger.info(f"✅ Processor stopped. Processed: {self.processed_count}, Errors: {self.error_count}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.is_running = False
    
    async def _process_messages(self):
        """Main message processing loop"""
        logger.info(f"🔄 Starting message processing loop...")
        logger.info(f"📡 Polling SQS queue: {self.config.aws.sqs_queue_url}")
        
        while self.is_running:
            try:
                # Receive messages from SQS (long polling)
                response = self.sqs_client.receive_message(
                    QueueUrl=self.config.aws.sqs_queue_url,
                    MaxNumberOfMessages=10,  # Process up to 10 messages at once
                    WaitTimeSeconds=20,      # Long polling (matches our validation system)
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                
                if messages:
                    logger.info(f"📨 Received {len(messages)} messages")
                    await self._process_message_batch(messages)
                else:
                    # No messages, brief pause before next poll
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {str(e)}")
                self.error_count += 1
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _process_message_batch(self, messages: list):
        """Process a batch of SQS messages"""
        tasks = []
        
        for message in messages:
            task = asyncio.create_task(self._process_single_message(message))
            tasks.append(task)
        
        # Process all messages concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        success_count = sum(1 for r in results if r is True)
        error_count = len(results) - success_count
        
        logger.info(f"✅ Batch processed: {success_count} success, {error_count} errors")
    
    async def _process_single_message(self, message: Dict[str, Any]) -> bool:
        """Process a single SQS message containing S3 event notification"""
        message_id = message.get('MessageId', 'unknown')
        receipt_handle = message['ReceiptHandle']
        
        try:
            # Parse S3 event notification
            body = json.loads(message['Body'])
            
            # Handle both direct S3 events and SNS-wrapped events
            if 'Records' in body:
                records = body['Records']
            elif 'Message' in body:
                # SNS wrapped message
                sns_message = json.loads(body['Message'])
                records = sns_message.get('Records', [])
            else:
                logger.error(f"❌ Unknown message format in {message_id}")
                return False
            
            success_count = 0
            total_records = len(records)
            
            # Process each S3 record
            for record in records:
                if record.get('eventSource') != 'aws:s3':
                    continue
                    
                bucket_name = record['s3']['bucket']['name']
                object_key = record['s3']['object']['key']
                
                logger.debug(f"Processing S3 object: s3://{bucket_name}/{object_key}")
                
                # Download and process the file
                if await self._process_s3_file(bucket_name, object_key):
                    success_count += 1
            
            if success_count == total_records:
                # Delete message from SQS (acknowledge processing)
                self.sqs_client.delete_message(
                    QueueUrl=self.config.aws.sqs_queue_url,
                    ReceiptHandle=receipt_handle
                )
                
                self.processed_count += success_count
                logger.info(f"✅ Successfully processed {success_count}/{total_records} records")
                return True
            else:
                # Message will be retried or sent to DLQ
                logger.error(f"❌ Failed to process message {message_id}: {success_count}/{total_records} successful")
                self.error_count += (total_records - success_count)
                return False
                
        except Exception as e:
            logger.error(f"❌ Error processing message {message_id}: {str(e)}")
            self.error_count += 1
            return False
    
    async def _process_s3_file(self, bucket_name: str, object_key: str) -> bool:
        """Download and process a JSON file from S3"""
        try:
            # Download the file from S3
            logger.debug(f"Downloading s3://{bucket_name}/{object_key}")
            
            response = self.s3_client.get_object(Bucket=bucket_name, Key=object_key)
            file_content = response['Body'].read().decode('utf-8')
            
            # Parse JSON
            try:
                movie_data_dict = json.loads(file_content)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON in s3://{bucket_name}/{object_key}: {str(e)}")
                return False
            
            # Validate and create Movie object
            try:
                movie_data = Movie(**movie_data_dict)
            except ValidationError as e:
                logger.error(f"❌ Validation failed for s3://{bucket_name}/{object_key}: {str(e)}")
                return False
            
            # Extract provider info from object key
            provider_name = object_key.split('/')[1] if '/' in object_key else 'unknown'
            
            # Process the movie data
            return await self._process_movie_data(movie_data, provider_name, object_key)
            
        except ClientError as e:
            logger.error(f"❌ S3 error downloading s3://{bucket_name}/{object_key}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Error processing s3://{bucket_name}/{object_key}: {str(e)}")
            return False
    
    async def _process_movie_data(self, movie_data: Movie, provider_name: str, source_key: str) -> bool:
        """Process validated movie data"""
        try:
            logger.debug(f"Processing movie from provider {provider_name}: {movie_data.title}")
            
            # Check if movie already exists
            existing_movie = await self.movie_repo.get_movie_by_id(movie_data.id)
            
            if existing_movie:
                # Update existing movie
                logger.info(f"🔄 Updating existing movie: {movie_data.title}")
                updated_movie = await self.movie_repo.update_movie(movie_data)
                
                if updated_movie:
                    logger.info(f"✅ Updated movie: {movie_data.title} from {source_key}")
                    return True
                else:
                    logger.error(f"❌ Failed to update movie: {movie_data.title}")
                    return False
            else:
                # Create new movie
                logger.info(f"🆕 Creating new movie: {movie_data.title}")
                created_movie = await self.movie_repo.create_movie(movie_data)
                
                if created_movie:
                    logger.info(f"✅ Created movie: {movie_data.title} from {source_key}")
                    return True
                else:
                    logger.error(f"❌ Failed to create movie: {movie_data.title}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error processing movie data: {str(e)}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for monitoring"""
        health = {
            "status": "healthy" if self.is_running else "stopped",
            "timestamp": datetime.utcnow().isoformat(),
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "services": {}
        }
        
        # Check service health
        try:
            db_healthy = await self.database.health_check()
            health["services"]["database"] = "healthy" if db_healthy else "unhealthy"
        except:
            health["services"]["database"] = "error"
        
        # Elasticsearch removed - using PostgreSQL for all queries
        health["services"]["search"] = "postgresql-based"
        
        try:
            # Test SQS connectivity
            self.sqs_client.get_queue_attributes(
                QueueUrl=self.config.aws.sqs_queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            health["services"]["sqs"] = "healthy"
        except:
            health["services"]["sqs"] = "error"
        
        return health


async def main():
    """Main entry point"""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.app.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🎬 Movie Data Processor v1.0.0")
    
    processor = DataProcessor()
    
    try:
        await processor.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        await processor.stop()


if __name__ == "__main__":
    asyncio.run(main())
