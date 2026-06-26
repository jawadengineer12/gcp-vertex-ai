# services/vector_store.py
import logging
from google.cloud import aiplatform_v1
from config.config import AppConfig

logger = logging.getLogger(__name__)


class VertexVectorStore:
    """
    Thin wrapper around the Vertex AI Vector Search MatchServiceClient.
    Handles connection setup and neighbor queries.
    """

    def __init__(self) -> None:
        client_options = {"api_endpoint": AppConfig.API_ENDPOINT}
        self.vector_search_client = aiplatform_v1.MatchServiceClient(
            client_options=client_options
        )
        self.index_endpoint = AppConfig.INDEX_ENDPOINT
        self.deployed_index_id = AppConfig.DEPLOYED_INDEX_ID
        logger.info(
            "VertexVectorStore initialized | endpoint=%s | deployed_id=%s",
            self.index_endpoint,
            self.deployed_index_id,
        )

    def find_nearest_neighbors(
        self, query_embedding: list[float], k: int = 10
    ) -> list[str]:
        """
        Queries the Vertex AI Vector Search index for top-k neighbors.
        Returns a list of datapoint IDs (stable unique IDs).
        """
        datapoint = aiplatform_v1.IndexDatapoint(
            feature_vector=query_embedding)
        query = aiplatform_v1.FindNeighborsRequest.Query(
            datapoint=datapoint,
            neighbor_count=k,
        )
        request = aiplatform_v1.FindNeighborsRequest(
            index_endpoint=self.index_endpoint,
            deployed_index_id=self.deployed_index_id,
            queries=[query],
            return_full_datapoint=False,
        )

        try:
            response = self.vector_search_client.find_neighbors(request)
        except Exception as e:
            logger.error("Vector Search query failed: %s", str(e))
            raise

        results = []
        if response.nearest_neighbors:
            for neighbor in response.nearest_neighbors[0].neighbors:
                results.append(neighbor.datapoint.datapoint_id)

        logger.info("Vector Search returned %d neighbor IDs.", len(results))
        return results
