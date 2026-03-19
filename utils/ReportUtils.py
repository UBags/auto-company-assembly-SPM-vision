# from reportlab.lib.colors import Color
# from reportlab.pdfgen.canvas import Canvas
# from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Frame, Spacer
# from reportlab.lib import colors
# from reportlab.lib.units import cm, inch, mm
# from reportlab.lib.pagesizes import letter, A3, A4, landscape, portrait
# from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
# from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
# from reportlab.pdfgen import canvas
# from utils.CosThetaFileUtils import createDirectory
# from utils.CosThetaPrintUtils import *
# from BaseUtils import getCurrentTime
#
#
# class NumberedPageCanvas(canvas.Canvas):
#     """
#     http://code.activestate.com/recipes/546511-page-x-of-y-with-reportlab/
#     http://code.activestate.com/recipes/576832/
#     http://www.blog.pythonlibrary.org/2013/08/12/reportlab-how-to-add-page-numbers/
#     """
#     width, height = landscape(A4)
#
#     def __init__(self, *args, **kwargs):
#         """Constructor"""
#         super().__init__(*args, **kwargs)
#         self.pages = []
#
#     def showPage(self):
#         """
#         On a page break, add information to the list
#         """
#         self.pages.append(dict(self.__dict__))
#         self._startPage()
#
#     def save(self):
#         """
#         Add the page number to each page (page x of y)
#         """
#         page_count = len(self.pages)
#
#         for page in self.pages:
#             self.__dict__.update(page)
#             self.draw_page_number(page_count)
#             super().showPage()
#
#         super().save()
#
#     def draw_page_number(self, page_count):
#         """
#         Add the page number
#         """
#         page = f"Page {self._pageNumber} of {page_count}"
#         self.setFont("Times-Bold", 11)
#         self.setFillColor(colors.gray)
#         self.setStrokeColor('#5B80B2')
#         self.drawRightString(NumberedPageCanvas.width - 75, 10, page)
#
#
# class ReportBuilder(object):
#
#     styles = getSampleStyleSheet()
#
#     def __init__(self, baseDir : str, relativeDirectory : str, baseFileName : str, contentAboveTable : str, data : list, columnSpacingProportions : list, headerBackground : Color = colors.lightblue, textBackground : Color = colors.white):
#
#         self.baseDir = baseDir
#         self.relativeDirectory = relativeDirectory
#         self.baseFilename = baseFileName
#         self.contentAboveTable = contentAboveTable
#         self.data = data
#         self.columnSpacingProportions = columnSpacingProportions
#         self.headerBackground = headerBackground
#         self.textBackground = textBackground
#         self.width, self.height = landscape(A4)
#
#         # elements.append(tableThatSplitsOverPages)
#
#
#
#     # ----------------------------------------------------------------------
#     def createAndSaveReport(self):
#         """
#         Run the report
#         """
#         try:
#             finalDirectory = f"{self.baseDir}{self.relativeDirectory}"
#             try:
#                 createDirectory(finalDirectory)
#             except:
#                 pass
#             self.pdfReportPath = f"{finalDirectory}{self.baseFilename}-{getCurrentTime()}.pdf"
#
#             doc = SimpleDocTemplate(self.pdfReportPath,
#                                          pagesize=landscape(A4),
#                                          rightMargin=10,
#                                          leftMargin=10,
#                                          topMargin=38,
#                                          bottomMargin=23)
#
#             story = [Spacer(1, 1.5 * inch)]
#
#             if self.data is not None:
#                 totalWidth : int = 24
#                 colWidths = []
#                 total = 0
#                 nColumns=len(self.columnSpacingProportions)
#                 for i in self.columnSpacingProportions:
#                     total += i
#                 for i in self.columnSpacingProportions:
#                     colWidths.append(i * totalWidth * cm/ total)
#
#                 tableThatSplitsOverPages = Table(self.data, colWidths=colWidths, repeatRows=1)
#                 tableThatSplitsOverPages.hAlign = 'CENTER'
#
#                 tblStyle = TableStyle([ ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
#                                         ('VALIGN',(0,0),(-1,-1),'TOP'),
#                                         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#                                         ('FONT', (0,0), (-1,0), 'Courier-Bold'),
#                                         ('LINEBELOW',(0,0),(-1,-1),1,colors.black),
#                                         ('FONT', (0,-1), (-1,-1), 'Courier'),
#                                         ('BOX',(0,0),(-1,-1),1,colors.black),
#                                         ('BOX',(0,0),(0,-1),1,colors.black),
#                                         ('LINEBEFORE', (0, 0), (-1, -1), 1, colors.black),
#                                         ('FONTSIZE', (0,0),(-1,-1), 9)])
#                 tblStyle.add('BACKGROUND',(0,0),(nColumns-1,0),self.headerBackground)
#                 tblStyle.add('BACKGROUND',(0,1),(-1,-1),self.textBackground)
#                 tableThatSplitsOverPages.setStyle(tblStyle)
#                 story.append(tableThatSplitsOverPages)
#
#             story.append(Spacer(1, 1 * inch))
#             totalWidth : int = 24
#             colWidths = [24*cm]
#             nColumns = 1
#             reviewedByTable = Table([['Reviewed By :']], colWidths=colWidths, repeatRows=0)
#             reviewedByTable.hAlign = 'LEFT'
#
#             tblStyle = TableStyle([ ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
#                                     ('VALIGN',(0,0),(-1,-1),'TOP'),
#                                     ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#                                     ('FONT', (0,0), (-1,0), 'Courier-Bold'),
#                                     ('FONT', (0,-1), (-1,-1), 'Courier-Bold'),
#                                     ('FONTSIZE', (0,0),(-1,-1), 12)])
#             tblStyle.add('BACKGROUND',(0,0),(nColumns-1,0),self.textBackground)
#             tblStyle.add('BACKGROUND',(0,1),(-1,-1),self.textBackground)
#             reviewedByTable.setStyle(tblStyle)
#             story.append(reviewedByTable)
#
#             doc.build(story, onFirstPage=self.createContentAboveTable, onLaterPages=self.header_footer, canvasmaker=NumberedPageCanvas)
#         except Exception as e:
#             printBoldRed(f"Could not build report dues to {e}")
#
#     def header_footer(self, docCanvas, doc):
#         docCanvas.saveState()
#         docCanvas.setFont("Times-Bold", 11)
#         docCanvas.setFillColor(colors.gray)
#         docCanvas.setStrokeColor('#5B80B2')
#         docCanvas.drawCentredString(self.width / 2, self.height - 20, self.pdfReportPath)
#         # page = f"Page {self._pageNumber} of {page_count}"
#         # self.setFont("Times-Bold", 11)
#         # self.setFillColor(colors.gray)
#         # self.setStrokeColor('#5B80B2')
#         # self.drawRightString(NumberedPageCanvas.width - 75, 10, page)
#
#     # ----------------------------------------------------------------------
#     def createContentAboveTable(self, docCanvas, doc):
#         """
#         Create the document
#         """
#         self.c = docCanvas
#
#         self.c.setFont("Times-Bold", 11)
#         self.c.setFillColor(colors.gray)
#         self.c.setStrokeColor('#5B80B2')
#         self.c.drawCentredString(self.width / 2, self.height - 20, self.pdfReportPath)
#
#         normal = self.styles["Normal"]
#
#         header_text = f"<b>{self.contentAboveTable}</b>"
#         p = Paragraph(header_text, normal)
#         if self.data is not None:
#             p.wrapOn(self.c, self.width, self.height - 100)
#             p.drawOn(self.c, 30, self.height - 100)
#         else:
#             p.wrapOn(self.c, self.width, self.height - 200)
#             p.drawOn(self.c, 30, self.height - 200)
#
#         # ptext = """Lorem ipsum dolor sit amet, consectetur adipisicing elit,
#         # sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
#         # Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris
#         # nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in
#         # reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
#         # pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
#         # culpa qui officia deserunt mollit anim id est laborum."""
#         #
#         # p = Paragraph(ptext, style=normal)
#         # p.wrapOn(self.c, self.width - 50, self.height)
#         # p.drawOn(self.c, 30, self.height - 100)
#         #
#         # ptext = """
#         # At vero eos et accusamus et iusto odio dignissimos ducimus qui
#         # blanditiis praesentium voluptatum deleniti atque corrupti quos dolores
#         # et quas molestias excepturi sint occaecati cupiditate non provident,
#         # similique sunt in culpa qui officia deserunt mollitia animi, id est laborum
#         # et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio.
#         # Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit
#         # quo minus id quod maxime placeat facere possimus, omnis voluptas assumenda est,
#         # omnis dolor repellendus. Temporibus autem quibusdam et aut officiis debitis aut
#         # rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et
#         # molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus,
#         # ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis
#         # doloribus asperiores repellat.
#         # """
#         # p = Paragraph(ptext, style=normal)
#         # p.wrapOn(self.c, self.width - 50, self.height)
#         # p.drawOn(self.c, 30, self.height - 175)
#
#
# # ----------------------------------------------------------------------
# # if __name__ == "__main__":
# #     column1Heading = "COLUMN ONE HEADING"
# #     column2Heading = "COLUMN TWO HEADING"
# #     # Assemble data for each column using simple loop to append it into data list
# #     data = [[column1Heading, column2Heading]]
# #     for i in range(1, 100):
# #         data.append([str(i), str(i)])
# #
# #     rb = ReportBuilder(baseDir="C:/Temp/Reports/", relativeDirectory="RelDir/", baseFileName="AuditReport_Sorted_by-Date", contentAboveTable="Some Long Content<br />Some Long Content<br />Some Long Content<br />Some Long Content<br />Some Long Content<br />", data = data, columnSpacingProportions = [1, 1])
# #     rb.createAndSaveReport()
