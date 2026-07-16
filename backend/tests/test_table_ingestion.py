import unittest

from ingest.loader import table_to_row_documents


class TableIngestionTests(unittest.TestCase):
    def test_creates_one_self_contained_document_per_row(self):
        table = [
            ["Chương trình", "Mức học phí"],
            ["Khoa học máy tính, KT Cơ điện tử", "630"],
            ["Toán tin, Quản trị kinh doanh, Kế toán", "600"],
        ]
        docs = table_to_row_documents(
            table,
            plain_text=(
                "I. Các chương trình đào tạo đại học chính quy\n"
                "1) Các chương trình đào tạo chuẩn\n"
                "Mức học phí được tính theo đơn vị nghìn đồng.\n"
                "Chương trình Mức học phí"
            ),
            base_metadata={
                "source": "hoc_phi.pdf",
                "page": 3,
                "document_type": "hoc_phi",
                "is_table": False,
            },
            table_index=1,
        )

        self.assertEqual(len(docs), 2)
        self.assertIn("Khoa học máy tính, KT Cơ điện tử", docs[0].page_content)
        self.assertIn("Mức học phí: 630", docs[0].page_content)
        self.assertIn("Đơn vị: nghìn đồng/TCHP", docs[0].page_content)
        self.assertNotIn("Toán tin", docs[0].page_content)
        self.assertEqual(docs[0].metadata["table_row"], 1)

    def test_forward_fills_vertically_merged_cells(self):
        table = [
            ["Chương trình", "LLCT, GDTC, GDQP-AN", "Các học phần khác"],
            ["Global ICT", "700", "850"],
            ["Chương trình tiên tiến", None, "1020"],
            ["Đào tạo tài năng", "650", None],
        ]
        docs = table_to_row_documents(
            table,
            plain_text=(
                "2) Các chương trình đào tạo đặc biệt và chương trình ELITECH\n"
                "Đơn vị nghìn đồng\n"
                "Chương trình LLCT, GDTC, GDQP-AN Các học phần khác"
            ),
            base_metadata={
                "source": "hoc_phi.pdf",
                "page": 3,
                "document_type": "hoc_phi",
                "is_table": False,
            },
            table_index=1,
        )

        self.assertIn("LLCT, GDTC, GDQP-AN: 700", docs[1].page_content)
        self.assertIn("Các học phần khác: 1020", docs[1].page_content)
        self.assertIn("LLCT, GDTC, GDQP-AN: 650", docs[2].page_content)
        self.assertIn("Các học phần khác: 650", docs[2].page_content)


if __name__ == "__main__":
    unittest.main()
