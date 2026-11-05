from ask311.retrieval import ExampleIndex
from ask311.topics import topic_for


def test_renamed_types_share_a_topic():
    # The city renamed this type between 2024 and 2025; both must land in the same topic.
    assert topic_for("Road Pothole / Road Damage") == topic_for("Road - Pot hole") == "Potholes and road damage"
    assert topic_for("Residential Bin Lid Damaged") == topic_for("Residential: Bin: Repair or Replace Lid") == "Bins"


def test_rule_order():
    assert topic_for("Sidewalk - Graffiti Complaint") == "Graffiti and postering"
    assert topic_for("Res / Garbage / Not Picked Up") == "Missed collection"
    assert topic_for("All / Hazardous Waste / Not Picked Up") == "Hazardous waste"
    assert topic_for("Unknown - SRVCR") == "Other"


def test_retrieval_finds_similar_question():
    hits = ExampleIndex().search("busiest day for potholes", k=1)
    assert "Potholes" in hits[0]["sql"]
